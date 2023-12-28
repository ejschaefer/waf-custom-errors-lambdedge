# Dynamic Error Page Generation for AWS WAF

This project demonstrates how to use Lambda@Edge to dynamically generate error pages for AWS WAF. Using Lambda@Edge the id of a request blocked by AWS WAF is dynamically embedded into an error page and sent back to the client.


## Why?

AWS WAF provides limited support for custom error pages (https://docs.aws.amazon.com/waf/latest/developerguide/customizing-the-response-for-blocked-requests.html)

1. Default error response for blocked requests is a generic, unbranded page. This page does include the id of the blocked request which WAF operators can use in log investigations
2. Custom error pages can be configured using CloudFront to respond with error pages matching the website's design element. These pages, however, do not include the id of the blocked request.
   1. https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/GeneratingCustomErrorResponses.html
3. AWS WAF custom response can be configured to send a static error page back to the client. The blocked request id is also lost when using this option.