from aws_cdk import (
    Duration,
    Stack,
    CfnOutput,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_wafv2 as wafv2
)

from constructs import Construct

class WebStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc(self, "VPC", max_azs=2)

        cluster = ecs.Cluster(
            self, 'fargate-service-autoscaling',
            vpc=vpc
        )

        # Create Fargate Service
        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "sample-app",
            cluster=cluster,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_registry("amazon/amazon-ecs-sample")
            )
        )

        fargate_service.service.connections.security_groups[0].add_ingress_rule(
            peer = ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection = ec2.Port.tcp(80),
            description="Allow http inbound from VPC"
        )

        # Setup AutoScaling policy
        scaling = fargate_service.service.auto_scale_task_count(
            max_capacity=2
        )

        scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=50,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60),
        )

        CfnOutput(
            self, "LoadBalancerDNS",
            value=fargate_service.load_balancer.load_balancer_dns_name
        )           

        cf_distribution = cloudfront.Distribution(self, "WebDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.LoadBalancerV2Origin(fargate_service.load_balancer.load_balancer_arn),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS
            )
            ,comment = 'Website on Fargate'
        )

        CfnOutput(self, "CloudFrontURL",
                  value=cf_distribution.domain_name)
        
        waf_rules = []

        test_block_rule = wafv2.CfnWebACL.RuleProperty(self, id="Test-Block-Rule",
            name="Test-Block-Rule",
            priority=1,
            action=wafv2.CfnWebACL.RuleActionProperty(block={}),
            statement=wafv2.CfnWebACL.StatementOneProperty(
                byte_match_statement=wafv2.CfnWebACL.ByteMatchStatementProperty(
                    field_to_match=wafv2.CfnWebACL.FieldToMatchProperty(query_string={}),
                    positional_constraint="EXACTLY",
                    search_string="BLOCK=true",
                    text_transformation="NONE"
                )
            )
        )
        
        waf_rules.append(test_block_rule)

        wafacl = wafv2.CfnWebACL(self, id="WAF",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow=wafv2.CfnWebACL.AllowActionProperty(), block=None),
            ##
            ## The scope of this Web ACL.
            ## Valid options: CLOUDFRONT, REGIONAL.
            ## For CLOUDFRONT, you must create your WAFv2 resources
            ## in the US East (N. Virginia) Region, us-east-1
            ## https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-wafv2-webacl.html#cfn-wafv2-webacl-scope
            ##
            scope="CLOUDFRONT",
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name                ="waf-cloudfront",
                sampled_requests_enabled   =True
            ),
            rules=waf_rules
        )
    @property
    def cf_distribution(self):
        return self.cf_distribution