#!/usr/bin/env python3
import os

import aws_cdk as cdk

from infrastructure.web_stack import WebStack
from infrastructure.custom_error_page import CustomErrorPage


app = cdk.App()

## must create WAFv2 resources for Cloudfront scope in us-east-1
##https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-wafv2-webacl.html#cfn-wafv2-webacl-scope

web_app = WebStack(app, "WebStack")

error_page = CustomErrorPage(app, "ErrorPageStack", cf_distribution=web_app.cf_distribution)

app.synth()
