from aws_cdk import (
    Duration,
    Stack,
    CfnOutput,
    RemovalPolicy,
    custom_resources,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_s3 as s3,
    aws_lambda as _lambda
)
from constructs import Construct
import datetime

class CustomErrorPage(Stack):

    def __init__(self, scope: Construct, construct_id: str, cf_distribution: cloudfront.IDistribution, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        lambda_edge = _lambda.Function(self, 'LambdaEdgePageGenerator',
            runtime = _lambda.Runtime.PYTHON_3_11,
            handler = 'handler.lambda_handler',
            code = _lambda.Code.from_asset('lambda/page_generator'),
            timeout=Duration.seconds(30)
        )
        
        ddb_params_table = dynamodb.Table(self, 'DDBParamsTable',
            table_name='LambdaEdgeParameters',
            partition_key=dynamodb.Attribute(name='pk', type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        ) 

        ddb_params_table.grant_read_data(lambda_edge)

        error_content_bucket = s3.Bucket(self,
            "CustomErrorContent",
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            object_ownership=s3.ObjectOwnership.OBJECT_WRITER,
            auto_delete_objects=True,
        )

        origin_access_identity = cloudfront.OriginAccessIdentity(
            self,
            f'{construct_id}OriginAccessIdentity',
            comment="Allow S3 Read-Access from CloudFront"
        )

        error_content_bucket.grant_read(origin_access_identity)

        ddb_seed = custom_resources.AwsCustomResource(self, 'ddbInitData',
            on_create=custom_resources.AwsSdkCall(
                service='DynamoDB',
                action='putItem',
                parameters={
                    'TableName': ddb_params_table.table_name,
                    'Item': {
                        'pk': {'S': 'ErrorPageBucketName'},
                        'value': {'S': error_content_bucket.bucket_name}
                    }
                },
                physical_resource_id=custom_resources.PhysicalResourceId.of(datetime.date.now().toString()),
            ),
            policy=custom_resources.AwsCustomResourcePolicy.from_sdk_calls(
                resources=[ddb_params_table.table_arn]
            )
        )
        
        # hosting_bucket.add_to_resource_policy(
        #     iam.PolicyStatement(
        #         actions=["s3:GetObject"],
        #         effect=iam.Effect.ALLOW,
        #         resources=[hosting_bucket.arn_for_objects("*")],
        #         principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
        #         conditions={
        #             "StringEquals": {"AWS:SourceArn": cf_distribution.distribution_arn}
        #         }
        #     )
        # )

               
        # origin_access_control = cloudfront.CfnOriginAccessControl(self, "OriginAccessControl",
        #     origin_access_control_config={
        #             "name": "DynamicContent",
        #             "originAccessControlOriginType": "s3",
        #             "signingBehavior": "always",
        #             "signingProtocol": "sigv4"
        #     }
        # )

        cf_distribution.error_responses.append(
            cloudfront.ErrorResponse(
                http_status=403,
                response_http_status=200,
                ttl=Duration.seconds(0),
                response_page_path="/error/404.html",
            )
        )

        error_behavior=cloudfront.BehaviorOptions(
            origin=origins.S3Origin(
                bucket=error_content_bucket,
                origin_access_identity=origin_access_identity
            ),
            compress=True,
            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
            
            edge_lambdas=[cloudfront.EdgeLambda(
                function_version=lambda_edge.current_version,
                event_type=cloudfront.LambdaEdgeEventType.VIEWER_REQUEST
            )]
        )
        cf_distribution.add_behavior("/error/404.html", error_behavior)
