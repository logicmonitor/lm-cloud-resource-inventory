<#
.SYNOPSIS
This solution is provided by LogicMonitor in order to collect cloud resource counts within an AWS environment, for LogicMonitor licensing.

.DESCRIPTION
This script performs the following tasks:
1. Enumerates AWS resources across specified regions and/or accounts
2. Categorizes each resource as IaaS, PaaS, or Non-compute
3. Provides a summary count of resources in each category

It offers flexibility in scope, allowing users to focus on specific regions or 
accounts within an AWS Organization, and delivers a comprehensive overview of 
cloud resource distribution.

.PARAMETER Regions
Comma-separated list of AWS regions to process. If not provided, all regions will be processed.

.PARAMETER DetailedResults
Switch to include additional resource details as part of the detailed export.

.PARAMETER PassThru
Switch to return the results as a PowerShell object as well as writing to a file. This allows for further processing of the data within PowerShell.

.PARAMETER GlobalRegion
The AWS region used to query global resources like S3 buckets and CloudFront distributions. These resources are not tied to a specific region. By default us-east-1 is utilized.

.PARAMETER OrganizationalUnitId
The AWS Organizations Organizational Unit (OU) ID to process. This parameter is used to retrieve all accounts within the specified OU and its sub-OUs.

.PARAMETER AssumeRole
The IAM role name to assume in member accounts when processing resources across an organizational unit. This role should have the necessary permissions to enumerate resources in the member accounts.

.PARAMETER OutputFile
The name of the CSV file to export the results. Default is "aws_resource_count_output.csv".

.EXAMPLE
.\get_aws_resource_counts.ps1 -Regions "us-east-1,us-west-2" -OutputFile "custom_output.csv"

.EXAMPLE
.\get_aws_resource_counts.ps1 -DetailedResults -PassThru

.EXAMPLE
.\get_aws_resource_counts.ps1 -OrganizationalUnitId "ou-1234-5678abcd" -AssumeRole "OrganizationAccountAccessRole" -OutputFile "ou_resource_counts.csv"

.EXAMPLE
.\get_aws_resource_counts.ps1 -OrganizationalUnitId "ou-9876-dcba4321" -AssumeRole "CustomInventoryRole" -DetailedResults -Regions "us-east-1,us-west-2"

.EXAMPLE
$results = .\get_aws_ou_resource_counts.ps1 -OrganizationalUnitId "ou-abcd-1234efgh" -AssumeRole "ResourceInventoryRole" -PassThru -GlobalRegion "us-west-2"

.NOTES
Requires the AWS.Tools PowerShell modules to be installed and an active AWS connection.
#>
[CmdletBinding(DefaultParameterSetName = 'Default')]
param (
    [Parameter(HelpMessage = "Comma-separated list of AWS regions", ParameterSetName = 'Default')]
    [Parameter(ParameterSetName = 'OU')]
    [string]$Regions,

    [Parameter(HelpMessage = "Include full resource details as part of inventory export", ParameterSetName = 'Default')]
    [Parameter(ParameterSetName = 'OU')]
    [switch]$DetailedResults,

    [Parameter(HelpMessage = "Pass through export results as a PSObject", ParameterSetName = 'Default')]
    [Parameter(ParameterSetName = 'OU')]
    [switch]$PassThru,

    [Parameter(HelpMessage = "Output CSV file name", ParameterSetName = 'Default')]
    [Parameter(ParameterSetName = 'OU')]
    [string]$OutputFile = "aws_resource_count_output.csv",

    [Parameter(HelpMessage = "Region to use to query global namespaces such as S3", ParameterSetName = 'Default')]
    [Parameter(ParameterSetName = 'OU')]
    [string]$GlobalRegion = "us-east-1",

    [Parameter(Mandatory = $true, HelpMessage = "AWS Organizations OU ID", ParameterSetName = 'OU')]
    [string]$OrganizationalUnitId,

    [Parameter(Mandatory = $true, HelpMessage = "IAM Role to assume in member accounts", ParameterSetName = 'OU')]
    [string]$AssumeRole
)

#Service Region Availability based on https://api.regional-table.region-services.aws.a2z.com/index.json
$resourceTypeRegions = @{
    "AWS::ApiGateway::RestApi"                  = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ap-southeast-7"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "mx-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::ApiGatewayV2::Api"                    = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ap-southeast-7"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "mx-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::Athena::WorkGroup"                    = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ap-southeast-7"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "mx-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::Backup::BackupVault"                  = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ap-southeast-7"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "mx-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::DocDBElastic::Cluster"                = @(
        "ap-east-1",
        "ap-southeast-2",
        "ca-central-1",
        "eu-central-1",
        "eu-south-2",
        "eu-west-1",
        "eu-west-2",
        "eu-west-3",
        "sa-east-1",
        "us-gov-east-1",
        "af-south-1",
        "ap-northeast-1",
        "ap-south-1",
        "ap-south-2",
        "ap-southeast-1",
        "eu-south-1",
        "me-central-1",
        "us-east-1",
        "us-gov-west-1",
        "us-west-2",
        "ap-northeast-2",
        "cn-north-1",
        "cn-northwest-1",
        "us-east-2"
    )
    "AWS::DynamoDB::Table"                      = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ap-southeast-7"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "mx-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::EC2::NatGateway"                      = @(
        "ap-northeast-1",
        "ap-northeast-3",
        "ap-south-1",
        "ap-southeast-2",
        "eu-north-1",
        "eu-west-2",
        "eu-west-3",
        "me-central-1",
        "sa-east-1",
        "us-gov-west-1",
        "af-south-1",
        "ap-northeast-2",
        "ap-south-2",
        "ap-southeast-4",
        "ap-southeast-5",
        "ap-southeast-7",
        "il-central-1",
        "us-east-1",
        "us-east-2",
        "us-gov-east-1",
        "ap-east-1",
        "ap-southeast-1",
        "ap-southeast-3",
        "ca-west-1",
        "cn-north-1",
        "eu-central-2",
        "eu-south-1",
        "eu-south-2",
        "eu-west-1",
        "us-west-2",
        "ca-central-1",
        "cn-northwest-1",
        "eu-central-1",
        "me-south-1",
        "mx-central-1",
        "us-west-1"
    )
    "AWS::EC2::TransitGatewayAttachment"        = @(
        "ap-northeast-1",
        "ap-northeast-3",
        "ap-south-1",
        "ap-southeast-2",
        "eu-north-1",
        "eu-west-2",
        "eu-west-3",
        "me-central-1",
        "sa-east-1",
        "us-gov-west-1",
        "af-south-1",
        "ap-northeast-2",
        "ap-south-2",
        "ap-southeast-4",
        "ap-southeast-5",
        "ap-southeast-7",
        "il-central-1",
        "us-east-1",
        "us-east-2",
        "us-gov-east-1",
        "ap-east-1",
        "ap-southeast-1",
        "ap-southeast-3",
        "ca-west-1",
        "cn-north-1",
        "eu-central-2",
        "eu-south-1",
        "eu-south-2",
        "eu-west-1",
        "us-west-2",
        "ca-central-1",
        "cn-northwest-1",
        "eu-central-1",
        "me-south-1",
        "mx-central-1",
        "us-west-1"
    )
    "AWS::EC2::TransitGateway"                  = @(
        "ap-northeast-1",
        "ap-northeast-3",
        "ap-south-1",
        "ap-southeast-2",
        "eu-north-1",
        "eu-west-2",
        "eu-west-3",
        "me-central-1",
        "sa-east-1",
        "us-gov-west-1",
        "af-south-1",
        "ap-northeast-2",
        "ap-south-2",
        "ap-southeast-4",
        "ap-southeast-5",
        "ap-southeast-7",
        "il-central-1",
        "us-east-1",
        "us-east-2",
        "us-gov-east-1",
        "ap-east-1",
        "ap-southeast-1",
        "ap-southeast-3",
        "ca-west-1",
        "cn-north-1",
        "eu-central-2",
        "eu-south-1",
        "eu-south-2",
        "eu-west-1",
        "us-west-2",
        "ca-central-1",
        "cn-northwest-1",
        "eu-central-1",
        "me-south-1",
        "mx-central-1",
        "us-west-1"
    )
    "AWS::EC2::VPNConnection"                   = @(
        "ap-northeast-1",
        "ap-northeast-3",
        "ap-south-1",
        "ap-southeast-2",
        "eu-north-1",
        "eu-west-2",
        "eu-west-3",
        "me-central-1",
        "sa-east-1",
        "us-gov-west-1",
        "af-south-1",
        "ap-northeast-2",
        "ap-south-2",
        "ap-southeast-4",
        "ap-southeast-5",
        "ap-southeast-7",
        "il-central-1",
        "us-east-1",
        "us-east-2",
        "us-gov-east-1",
        "ap-east-1",
        "ap-southeast-1",
        "ap-southeast-3",
        "ca-west-1",
        "cn-north-1",
        "eu-central-2",
        "eu-south-1",
        "eu-south-2",
        "eu-west-1",
        "us-west-2",
        "ca-central-1",
        "cn-northwest-1",
        "eu-central-1",
        "me-south-1",
        "mx-central-1",
        "us-west-1"
    )
    "AWS::EC2::Volume"                          = @(
        "ap-northeast-1",
        "ap-northeast-3",
        "ap-south-1",
        "ap-southeast-2",
        "eu-north-1",
        "eu-west-2",
        "eu-west-3",
        "me-central-1",
        "sa-east-1",
        "us-gov-west-1",
        "af-south-1",
        "ap-northeast-2",
        "ap-south-2",
        "ap-southeast-4",
        "ap-southeast-5",
        "ap-southeast-7",
        "il-central-1",
        "us-east-1",
        "us-east-2",
        "us-gov-east-1",
        "ap-east-1",
        "ap-southeast-1",
        "ap-southeast-3",
        "ca-west-1",
        "cn-north-1",
        "eu-central-2",
        "eu-south-1",
        "eu-south-2",
        "eu-west-1",
        "us-west-2",
        "ca-central-1",
        "cn-northwest-1",
        "eu-central-1",
        "me-south-1",
        "mx-central-1",
        "us-west-1"
    )
    "AWS::EFS::FileSystem"                      = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ap-southeast-7"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "mx-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::ElasticBeanstalk::Environment"        = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ca-central-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-north-1"
        "eu-south-1"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-south-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::EMR::Cluster"                         = @(
        "af-south-1",
        "ap-southeast-1",
        "ap-southeast-3",
        "ap-southeast-4",
        "ca-central-1",
        "eu-north-1",
        "me-central-1",
        "me-south-1",
        "sa-east-1",
        "us-west-2",
        "ap-south-2",
        "ap-southeast-7",
        "ca-west-1",
        "cn-north-1",
        "cn-northwest-1",
        "eu-central-1",
        "eu-central-2",
        "eu-west-2",
        "eu-west-3",
        "us-gov-west-1",
        "ap-east-1",
        "ap-northeast-1",
        "ap-northeast-2",
        "ap-northeast-3",
        "ap-south-1",
        "ap-southeast-2",
        "eu-south-1",
        "eu-west-1",
        "mx-central-1",
        "us-gov-east-1",
        "ap-southeast-5",
        "eu-south-2",
        "il-central-1",
        "us-east-1",
        "us-east-2",
        "us-west-1"
    )
    "AWS::KinesisFirehose::DeliveryStream"      = @(
        "ap-southeast-4",
        "ap-southeast-7",
        "ca-central-1",
        "ca-west-1",
        "cn-northwest-1",
        "eu-west-1",
        "eu-west-3",
        "il-central-1",
        "me-central-1",
        "sa-east-1",
        "ap-northeast-1",
        "ap-northeast-2",
        "ap-south-1",
        "ap-southeast-2",
        "eu-north-1",
        "eu-west-2",
        "mx-central-1",
        "us-east-1",
        "us-east-2",
        "us-west-2",
        "af-south-1",
        "ap-northeast-3",
        "ap-south-2",
        "ap-southeast-5",
        "cn-north-1",
        "eu-central-2",
        "eu-south-2",
        "me-south-1",
        "us-gov-west-1",
        "us-west-1",
        "ap-east-1",
        "ap-southeast-1",
        "ap-southeast-3",
        "eu-central-1",
        "eu-south-1",
        "us-gov-east-1"
    )
    "AWS::KinesisVideo::Stream"                 = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-south-1"
        "ap-southeast-1"
        "ap-southeast-2"
        "ca-central-1"
        "cn-north-1"
        "eu-central-1"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-2"
    )
    "AWS::Kinesis::Stream"                      = @(
        "ap-southeast-4",
        "ap-southeast-7",
        "ca-central-1",
        "ca-west-1",
        "cn-northwest-1",
        "eu-west-1",
        "eu-west-3",
        "il-central-1",
        "me-central-1",
        "sa-east-1",
        "ap-northeast-1",
        "ap-northeast-2",
        "ap-south-1",
        "ap-southeast-2",
        "eu-north-1",
        "eu-west-2",
        "mx-central-1",
        "us-east-1",
        "us-east-2",
        "us-west-2",
        "af-south-1",
        "ap-northeast-3",
        "ap-south-2",
        "ap-southeast-5",
        "cn-north-1",
        "eu-central-2",
        "eu-south-2",
        "me-south-1",
        "us-gov-west-1",
        "us-west-1",
        "ap-east-1",
        "ap-southeast-1",
        "ap-southeast-3",
        "eu-central-1",
        "eu-south-1",
        "us-gov-east-1"
    )
    "AWS::ElasticLoadBalancing::LoadBalancer"   = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ap-southeast-7"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "mx-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::ElasticLoadBalancingV2::LoadBalancer" = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ap-southeast-7"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "mx-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::MediaConnect::Flow"                   = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-4"
        "ca-central-1"
        "eu-central-1"
        "eu-north-1"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "me-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-west-1"
        "us-west-2"
    )
    "AWS::MediaPackage::Channel"                = @(
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-4"
        "ca-central-1"
        "eu-central-1"
        "eu-north-1"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-west-1"
        "us-west-2"
    )
    "AWS::MediaPackage::PackagingGroup"         = @(
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-4"
        "ca-central-1"
        "eu-central-1"
        "eu-north-1"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-west-1"
        "us-west-2"
    )
    "AWS::Route53::HealthCheck"                 = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ap-southeast-7"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "mx-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::SES::ConfigurationSet"                = @(
        "af-south-1",
        "ap-northeast-1",
        "ap-northeast-3",
        "ap-southeast-1",
        "eu-west-2",
        "eu-west-3",
        "il-central-1",
        "sa-east-1",
        "us-gov-east-1",
        "us-gov-west-1",
        "ap-northeast-2",
        "ap-south-1",
        "ap-southeast-3",
        "eu-central-1",
        "eu-south-1",
        "eu-west-1",
        "me-south-1",
        "us-east-2",
        "us-west-1",
        "us-west-2",
        "ap-southeast-2",
        "ca-central-1",
        "eu-north-1",
        "us-east-1"
    )
    "AWS::SNS::Topic"                           = @(
        "ap-east-1",
        "ap-northeast-2",
        "ap-southeast-1",
        "ap-southeast-2",
        "ap-southeast-7",
        "eu-central-1",
        "eu-west-3",
        "me-central-1",
        "me-south-1",
        "us-gov-east-1",
        "ap-southeast-3",
        "ap-southeast-4",
        "ca-west-1",
        "cn-north-1",
        "eu-central-2",
        "eu-north-1",
        "eu-south-1",
        "eu-south-2",
        "mx-central-1",
        "sa-east-1",
        "af-south-1",
        "ap-northeast-1",
        "ap-northeast-3",
        "ap-south-1",
        "ap-south-2",
        "cn-northwest-1",
        "eu-west-2",
        "il-central-1",
        "us-east-1",
        "us-west-1",
        "ap-southeast-5",
        "ca-central-1",
        "eu-west-1",
        "us-east-2",
        "us-gov-west-1",
        "us-west-2"
    )
    "AWS::SQS::Queue"                           = @(
        "af-south-1",
        "ap-east-1",
        "ap-northeast-2",
        "ap-southeast-4",
        "cn-north-1",
        "eu-west-3",
        "il-central-1",
        "mx-central-1",
        "us-east-2",
        "us-west-1",
        "ap-south-1",
        "ap-south-2",
        "ap-southeast-1",
        "ap-southeast-3",
        "ap-southeast-7",
        "ca-west-1",
        "eu-central-2",
        "eu-west-1",
        "eu-west-2",
        "us-east-1",
        "ap-northeast-1",
        "ap-northeast-3",
        "ca-central-1",
        "cn-northwest-1",
        "eu-north-1",
        "eu-south-2",
        "me-central-1",
        "me-south-1",
        "sa-east-1",
        "us-gov-east-1",
        "ap-southeast-2",
        "ap-southeast-5",
        "eu-central-1",
        "eu-south-1",
        "us-gov-west-1",
        "us-west-2"
    )
    "AWS::StepFunctions::StateMachine"          = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ap-southeast-7"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "mx-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::CloudFront::Distribution"             = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ap-southeast-7"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "mx-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-west-1"
        "us-west-2"
    )
    "AWS::S3::Bucket"                           = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ap-southeast-7"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "mx-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::EC2::Instance"                        = @(
        "ap-northeast-1",
        "ap-northeast-3",
        "ap-south-1",
        "ap-southeast-2",
        "eu-north-1",
        "eu-west-2",
        "eu-west-3",
        "me-central-1",
        "sa-east-1",
        "us-gov-west-1",
        "af-south-1",
        "ap-northeast-2",
        "ap-south-2",
        "ap-southeast-4",
        "ap-southeast-5",
        "ap-southeast-7",
        "il-central-1",
        "us-east-1",
        "us-east-2",
        "us-gov-east-1",
        "ap-east-1",
        "ap-southeast-1",
        "ap-southeast-3",
        "ca-west-1",
        "cn-north-1",
        "eu-central-2",
        "eu-south-1",
        "eu-south-2",
        "eu-west-1",
        "us-west-2",
        "ca-central-1",
        "cn-northwest-1",
        "eu-central-1",
        "me-south-1",
        "mx-central-1",
        "us-west-1"
    )
    "AWS::ECS::Cluster"                         = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ap-southeast-7"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "mx-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::Lambda::Function"                     = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ap-southeast-7"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "mx-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::AppStream::Fleet"                     = @(
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-south-1"
        "ap-southeast-1"
        "ap-southeast-2"
        "ca-central-1"
        "eu-central-1"
        "eu-west-1"
        "eu-west-2"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-2"
    )
    "AWS::CloudSearchDomain"                    = @(
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "eu-central-1"
        "eu-west-1"
        "sa-east-1"
        "us-east-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::Glue::Job"                            = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ap-southeast-7"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "mx-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::AmazonMQ::Broker"                     = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ap-southeast-7"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "mx-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::MSK::Cluster"                         = @(
        "af-south-1",
        "ap-northeast-2",
        "ap-southeast-2",
        "ap-southeast-5",
        "cn-northwest-1",
        "eu-west-3",
        "me-central-1",
        "us-gov-east-1",
        "us-gov-west-1",
        "us-west-2",
        "ap-northeast-1",
        "ap-northeast-3",
        "ap-south-1",
        "ap-southeast-3",
        "ap-southeast-4",
        "ca-west-1",
        "eu-north-1",
        "me-south-1",
        "us-east-1",
        "us-east-2",
        "ap-east-1",
        "ap-south-2",
        "ca-central-1",
        "cn-north-1",
        "eu-central-2",
        "eu-south-1",
        "eu-west-2",
        "il-central-1",
        "sa-east-1",
        "us-west-1",
        "ap-southeast-1",
        "eu-central-1",
        "eu-south-2",
        "eu-west-1"
    )
    "AWS::OpenSearchService::Domain"            = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ap-southeast-7"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "mx-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::QuickSight::Dashboard"                = @(
        "af-south-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-south-1"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ca-central-1"
        "cn-north-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-2"
    )
    "AWS::QuickSight::Dataset"                  = @(
        "af-south-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-south-1"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ca-central-1"
        "cn-north-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-2"
    )
    "AWS::ElastiCache::CacheCluster"            = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ap-southeast-7"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "mx-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::FSx::FileSystem"                      = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::Bedrock::FoundationModels"            = @(
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ca-central-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-2"
    )
    "AWS::Redshift::Cluster"                    = @(
        "af-south-1"
        "ap-east-1"
        "ap-northeast-1"
        "ap-northeast-2"
        "ap-northeast-3"
        "ap-south-1"
        "ap-south-2"
        "ap-southeast-1"
        "ap-southeast-2"
        "ap-southeast-3"
        "ap-southeast-4"
        "ap-southeast-5"
        "ap-southeast-7"
        "ca-central-1"
        "ca-west-1"
        "cn-north-1"
        "cn-northwest-1"
        "eu-central-1"
        "eu-central-2"
        "eu-north-1"
        "eu-south-1"
        "eu-south-2"
        "eu-west-1"
        "eu-west-2"
        "eu-west-3"
        "il-central-1"
        "me-central-1"
        "me-south-1"
        "mx-central-1"
        "sa-east-1"
        "us-east-1"
        "us-east-2"
        "us-gov-east-1"
        "us-gov-west-1"
        "us-west-1"
        "us-west-2"
    )
    "AWS::RDS::DBInstance"                      = @(
        "ap-east-1",
        "ap-southeast-1",
        "ap-southeast-3",
        "ap-southeast-7",
        "ca-central-1",
        "cn-northwest-1",
        "mx-central-1",
        "sa-east-1",
        "us-east-1",
        "us-east-2",
        "af-south-1",
        "ap-northeast-2",
        "ap-southeast-5",
        "cn-north-1",
        "eu-central-2",
        "eu-south-1",
        "me-central-1",
        "me-south-1",
        "us-gov-west-1",
        "us-west-1",
        "ap-northeast-1",
        "ap-northeast-3",
        "ap-south-1",
        "ap-southeast-4",
        "eu-north-1",
        "eu-south-2",
        "eu-west-1",
        "eu-west-3",
        "il-central-1",
        "us-west-2",
        "ap-south-2",
        "ap-southeast-2",
        "ca-west-1",
        "eu-central-1",
        "eu-west-2",
        "us-gov-east-1"
    )
}

# Define resource types and their corresponding cmdlets
$resourceTypes = @{
    "Non-Compute" = @{
        "AWS::ApiGateway::RestApi"                  = "Get-AGRestApiList"
        "AWS::ApiGatewayV2::Api"                    = "Get-AG2ApiList"
        "AWS::Athena::WorkGroup"                    = "Get-ATHWorkGroupList"
        "AWS::Backup::BackupVault"                  = "Get-BAKBackupVaultList"
        "AWS::DocDBElastic::Cluster"                = "Get-DOCDBCluster"
        "AWS::DynamoDB::Table"                      = "Get-DDBTableList"
        "AWS::EC2::NatGateway"                      = "Get-EC2NatGateway"
        "AWS::EC2::TransitGatewayAttachment"        = "Get-EC2TransitGatewayAttachment"
        "AWS::EC2::TransitGateway"                  = "Get-EC2TransitGateway"
        "AWS::EC2::VPNConnection"                   = "Get-EC2VpnConnection"
        "AWS::EC2::Volume"                          = "Get-EC2Volume"
        "AWS::EFS::FileSystem"                      = "Get-EFSFileSystem"
        "AWS::ElasticBeanstalk::Environment"        = "Get-EBEnvironment"
        "AWS::EMR::Cluster"                         = "Get-EMRClusterList"
        "AWS::KinesisFirehose::DeliveryStream"      = "Get-KINFDeliveryStreamList"
        "AWS::KinesisVideo::Stream"                 = "Get-KVStreamList"
        "AWS::Kinesis::Stream"                      = "Get-KINStreamList"
        "AWS::ElasticLoadBalancing::LoadBalancer"   = "Get-ELBLoadBalancer"
        "AWS::ElasticLoadBalancingV2::LoadBalancer" = "Get-ELB2LoadBalancer"
        "AWS::MediaConnect::Flow"                   = "Get-EMCNFlowList"
        "AWS::MediaPackage::Channel"                = "Get-EMPChannelList"
        "AWS::MediaPackage::PackagingGroup"         = "Get-EMPVPackagingGroupList"
        "AWS::Route53::HealthCheck"                 = "Get-R53HealthCheckList"
        "AWS::SES::ConfigurationSet"                = "Get-SES2ConfigurationSetList"
        "AWS::SNS::Topic"                           = "Get-SNSTopic"
        "AWS::SQS::Queue"                           = "Get-SQSQueue"
        "AWS::StepFunctions::StateMachine"          = "Get-SFNStateMachineList"
        "AWS::CloudFront::Distribution"             = "Get-CFDistributionList"
        "AWS::S3::Bucket"                           = "Get-S3Bucket"
    }
    "IaaS"        = @{
        "AWS::EC2::Instance" = "Get-EC2Instance"
    }
    "PaaS"        = @{
        "AWS::ECS::Cluster"              = "Get-ECSClusterList"
        "AWS::Lambda::Function"          = "Get-LMFunctionList"
        "AWS::AppStream::Fleet"          = "Get-APSFleetList"
        "AWS::CloudSearchDomain"         = "Get-CSDomainNameList"
        "AWS::Glue::Job"                 = "Get-GLUEJobList"
        "AWS::AmazonMQ::Broker"          = "Get-MQBrokerList"
        "AWS::MSK::Cluster"              = "Get-MSKClusterList"
        "AWS::OpenSearchService::Domain" = "Get-OSDomainNameList"
        "AWS::QuickSight::Dashboard"     = "Get-QSDashboardList"
        "AWS::QuickSight::Dataset"       = "Get-QSDatasetList"
        "AWS::ElastiCache::CacheCluster" = "Get-ECCacheCluster"
        "AWS::FSx::FileSystem"           = "Get-FSXFileSystem"
        "AWS::Bedrock::FoundationModels" = "Get-BDRFoundationModelList"
        "AWS::Redshift::Cluster"         = "Get-RSCluster"
        "AWS::RDS::DBInstance"           = "Get-RDSDBInstance"
    }
}

# Define regions if not provided
$regionList = if ($Regions) { $Regions -split ',' | ForEach-Object { $_.Trim() } } else {
    @("us-east-1", "us-east-2", "us-west-1", "us-west-2", "eu-central-1", "eu-north-1",
        "eu-south-1", "eu-west-1", "eu-west-2", "eu-west-3", "ap-east-1", "ap-northeast-1",
        "ap-northeast-2", "ap-northeast-3", "ap-south-1", "ap-southeast-1", "ap-southeast-2",
        "ap-southeast-3", "af-south-1", "ca-central-1", "me-south-1", "sa-east-1")
}

function Invoke-AssumeRole {
    param (
        [string]$AccountId,
        [string]$RoleName
    )
    
    # Construct the ARN for the role to assume in the target account
    $roleArn = "arn:aws:iam::${AccountId}:role/${RoleName}"
    # Assume the role using AWS STS and retrieve temporary credentials
    $assumedRole = Use-STSRole -RoleArn $roleArn -RoleSessionName "ResourceInventorySession"
    
    return $assumedRole.Credentials
}

function Get-BedrockMetrics {
    param (
        [string]$Region,
        [object]$Credentials,
        [string]$Account
    )

    try {
        $params = @{
            Namespace            = 'AWS/Bedrock'
            Region               = $Region
            OwningAccount        = $Account
            IncludeLinkedAccount = $true
        }

        if ($Credentials) {
            $params['AccessKey'] = $Credentials.AccessKeyId
            $params['SecretKey'] = $Credentials.SecretAccessKey
            $params['SessionToken'] = $Credentials.SessionToken
        }

        # Query CloudWatch for metrics within the AWS/Bedrock namespace
        Write-Debug "Bedrock Metrics Params:"
        Write-Debug ($params | Out-String)

        $metrics = @()
        $metrics = Get-CWMetricList @params
        if ($metrics) {
            # Group metrics by the ModelId dimension to count distinct models in use
            $groupedMetrics = $metrics | 
                Where-Object { $_.Dimensions } | 
                Group-Object -Property { $_.Dimensions.Value } |
                Select-Object -Property @{
                    Name       = 'ModelId'; 
                    Expression = { $_.Name }
                }, @{
                    Name       = 'MetricCount'; 
                    Expression = { $_.Count }
                }

            return $groupedMetrics
        }
        else {
            Write-Host "No Bedrock models found in use for region $Region"
            return $null
        }

    }
    catch {
        Write-Warning "Error retrieving Bedrock metrics in region $Region`: $_"
        return $null
    }
}

function Get-AWSResources {
    param (
        [string[]]$Regions, # This is the list of regions requested by the user or default
        [string]$ResourceType,
        [string]$Cmdlet,
        [string]$Category,
        [object]$Credentials,
        [hashtable]$ResourceTypeRegionsMap,
        [string[]]$DisabledAccountRegions # Added: List of regions disabled for the current account
    )

    $allResources = @()
    $timeout = [TimeSpan]::FromMilliseconds(10000)
    
    # Determine Account ID once
    $Account = $null
    try {
        $stsParams = @{}
        if ($Credentials) { $stsParams['Credential'] = $Credentials }
        $Account = (Get-STSCallerIdentity @stsParams -ErrorAction Stop).Account
    }
    catch {
        $errorString = $_.ToString()
        Write-Warning "Failed to get Account ID for resource type $ResourceType. Skipping. Error: $($errorString)"
        return @() 
    }
    if (-not $Account) {
        Write-Warning "Account ID could not be determined for resource type $ResourceType. Skipping."
        return @()
    }

    Write-Host "Processing $ResourceType for Account $Account"

    # Sequentially process each specified region from the input $Regions list
    foreach ($region in $Regions) {
        # Use a local variable for resources in this region
        $resourcesInRegion = @() 
        Write-Host "Processing $ResourceType in region: $region for Account $Account"

        # --- BEGIN ACCOUNT DISABLED REGION CHECK ---
        if ($region -in $DisabledAccountRegions) {
            Write-Host "Skipping region $region for Account $Account as it is explicitly disabled in the account settings."
            continue # Skip this entire region for this account
        }
        # --- END ACCOUNT DISABLED REGION CHECK ---

        # --- BEGIN SERVICE REGION AVAILABILITY CHECK ---
        # Check if the resource type is defined in the map and if the current region is supported for it
        if ($ResourceTypeRegionsMap.ContainsKey($ResourceType)) {
            $supportedRegionsForService = $ResourceTypeRegionsMap[$ResourceType]
            if ($region -notin $supportedRegionsForService) {
                Write-Host "Skipping $ResourceType in region $region as it is not listed as available in resourceTypeRegions."
                continue # Skip to the next region for this resource type
            }
        }
        # If the resource type is NOT in the map, we proceed as before (assume available or let API call handle it)
        # --- END SERVICE REGION AVAILABILITY CHECK ---

        # Client config defined per region/call
        $clientConfig = @{
            Timeout = $timeout
        }

        try {
            # Special handling for Bedrock as it relies on metrics not direct listing
            if ($ResourceType -eq "AWS::Bedrock::FoundationModels") {
                # Use sequential call to Get-BedrockMetrics
                $bedrockParams = @{
                    Region  = $region
                    Account = $Account
                }
                if ($Credentials) {
                    $bedrockParams['Credentials'] = $Credentials
                }
                $resourcesInRegion = Get-BedrockMetrics @bedrockParams
            }
            else {
                # Build parameters for the target cmdlet
                $cmdletParams = @{
                    Region       = $region
                    ClientConfig = $clientConfig
                    ErrorAction  = 'Stop'
                }

                if ($Credentials) {
                    $cmdletParams['AccessKey'] = $Credentials.AccessKeyId
                    $cmdletParams['SecretKey'] = $Credentials.SecretAccessKey
                    $cmdletParams['SessionToken'] = $Credentials.SessionToken
                }

                if ($Cmdlet -like "*-QS*") {
                    $cmdletParams['AwsAccountId'] = $Account
                }
                
                # Dynamically invoke the specific AWS Tools cmdlet using splatting
                $resourcesInRegion = & $Cmdlet @cmdletParams
            }

            if ($resourcesInRegion) {
                # Add results to the main array, standardizing the output object
                $resourcesInRegion | ForEach-Object {
                    # Create the object to add
                    # Ensure we are adding the correct object structure based on what $resourcesInRegion contains
                    if ($ResourceType -eq "AWS::Bedrock::FoundationModels") {
                        # Assuming Get-BedrockMetrics returns objects ready to be counted (like ModelId)
                        # We need to count these later, so add a standard structure
                        $allResources += [PSCustomObject]@{
                            Region         = $region 
                            ResourceType   = $ResourceType
                            Category       = $Category
                            AccountId      = $Account
                            # Specific Bedrock details if needed from $_ (the bedrock metric object)
                            BedrockModelId = $_.ModelId # Example
                        } 
                    }
                    else {
                        # For other resources, add the standard object structure
                        $allResources += [PSCustomObject]@{
                            Region       = $region 
                            ResourceType = $ResourceType
                            Category     = $Category
                            AccountId    = $Account
                            # Specific details from $_ (the resource object) if DetailedResults is enabled
                        }
                    }
                }
            }
        }
        catch {
            # Keep the refined error handling
            $fullErrorString = $_.ToString()
            $errorMessage = $_.Exception.Message

            if ($errorMessage -notlike "*is not supported in this region*" -and
                $errorMessage -notlike "*Name or service not known*" -and 
                $errorMessage -notlike "*New domain creation not supported on this account*" -and
                $errorMessage -notlike "*is not subscribed for*") {
                Write-Warning "Error processing $ResourceType in region $region for Account $($Account): $($fullErrorString)" 
            }
        }
    } # End foreach region

    # Return the standard array
    return $allResources
}

# Function to recursively get accounts from an OU and its sub-OUs
function Get-RecursiveOrgAccounts {
    param (
        [Parameter(Mandatory = $true)]
        [string]$ParentId
    )

    $accounts = @()

    # Get accounts directly associated with the current ParentId (OU or Root)
    try {
        # Using original cmdlet name, verify based on AWS.Tools.Organizations version
        $directAccounts = Get-ORGAccountForParent -ParentId $ParentId -ErrorAction Stop 
        if ($directAccounts) {
            # The cmdlet returns Account objects, add the objects themselves
            $accounts += $directAccounts
        }
    }
    catch {
        # Use standard error formatting with intermediate variable
        $errorString = $_.ToString()
        Write-Warning ("Could not retrieve accounts for parent {0}: {1}" -f $ParentId, $errorString)
    }


    # Get child OUs under the current ParentId to enable recursion
    try {
        # Using original cmdlet name, verify based on AWS.Tools.Organizations version
        $childOUs = Get-ORGOrganizationalUnitList -ParentId $ParentId -ErrorAction Stop
        if ($childOUs) {
            foreach ($ou in $childOUs) {
                Write-Debug "Descending into OU: $($ou.Id) ($($ou.Name))"
                # Recursively call for each child OU
                $accounts += Get-RecursiveOrgAccounts -ParentId $ou.Id
            }
        }
    }
    catch {
        # Use standard error formatting with intermediate variable
        $errorString = $_.ToString()
        Write-Warning ("Could not retrieve child OUs for parent {0}: {1}" -f $ParentId, $errorString)
    }


    # Return unique accounts based on their ID
    return $accounts | Sort-Object -Property Id -Unique
}

# Main script execution
try {
    # Check AWS connection
    $currentIdentity = Get-STSCallerIdentity -ErrorAction Stop
    if (-not $currentIdentity) {
        throw "Failed to retrieve AWS identity. Please ensure you're connected to AWS."
    }
    Write-Host "Connected to AWS as: $($currentIdentity.Arn)"

    # Determine list of accounts to process
    $accountsToProcess = @()
    if ($OrganizationalUnitId -and $AssumeRole) {
        Write-Host "Recursively retrieving accounts under OU: $OrganizationalUnitId"
        # Ensure the correct credentials context is used for the Org call (should be management account)
        $accountsToProcess = Get-RecursiveOrgAccounts -ParentId $OrganizationalUnitId 
        Write-Host "Found $($accountsToProcess.Count) accounts in the specified OU hierarchy."
    }
    else {
        # If not OU mode, process the current account
        $currentAccountId = $currentIdentity.Account
        # Create a mock account object or just use the ID
        $accountsToProcess = @([PSCustomObject]@{Id = $currentAccountId; Name = "Current Account" }) 
        Write-Host "Processing current account: $currentAccountId"
    }

    $allResources = @()
    $totalAccounts = $accountsToProcess.Count
    $accountIndex = 0

    # Iterate through each account determined (either single or from OU)
    foreach ($account in $accountsToProcess) {
        $accountId = $account.Id # Assuming the object has an Id property
        $accountIndex++
        Write-Host "Processing Account [$accountIndex/$totalAccounts]: $accountId"
        
        $currentCredentials = $null # Credentials for the specific account loop
        $isAssumedRole = $false

        # Assume role if in OU mode and the current account is not the management account
        if ($OrganizationalUnitId -and $AssumeRole) {
            # Determine if the current account IS the management account to avoid unnecessary assume role
            # Note: This assumes Get-STSCallerIdentity returns the management account identity when run initially
            if ($accountId -ne $currentIdentity.Account) { 
                try {
                    Write-Host "Attempting to assume role $AssumeRole in account $accountId..."
                    $currentCredentials = Invoke-AssumeRole -AccountId $accountId -RoleName $AssumeRole
                    if ($currentCredentials) {
                        Write-Host "Successfully assumed role in account $accountId"
                        $isAssumedRole = $true
                    }
                    else {
                        Write-Warning "Failed to assume role in account $accountId (Invoke-AssumeRole returned null). Skipping account."
                        continue # Skip to next account
                    }
                }
                catch {
                    # Explicitly capture error string
                    $errorString = $_.ToString()
                    Write-Warning "Error assuming role in account $($accountId): $($errorString). Skipping account."
                    continue # Skip to next account
                }
            }
            else {
                Write-Host "Processing management account $accountId with initial credentials."
                # Use initial credentials ($null indicates default context for Get-AWSResources)
                $currentCredentials = $null
            }
        }
        else {
            # Running in single account mode, use default credentials (null signals Get-AWSResources to use default)
            $currentCredentials = $null
        }

        # --- BEGIN Fetch Disabled Regions for Account ---
        $disabledRegionsForAccount = @()
        try {
            $acctRegionParams = @{ ErrorAction = 'Stop' }
            if ($currentCredentials) {
                $acctRegionParams['AccessKey'] = $currentCredentials.AccessKeyId
                $acctRegionParams['SecretKey'] = $currentCredentials.SecretAccessKey
                $acctRegionParams['SessionToken'] = $currentCredentials.SessionToken
            }
            # Fetch all regions status for the account
            $accountRegionStatus = Get-ACCTRegionList @acctRegionParams 
            # Filter for DISABLED regions
            $disabledRegionsForAccount = $accountRegionStatus | Where-Object { $_.RegionOptStatus -eq 'DISABLED' } | Select-Object -ExpandProperty RegionName
            if ($disabledRegionsForAccount) {
                Write-Host "Account $accountId has the following regions explicitly disabled: $($disabledRegionsForAccount -join ', ')"
            }
        }
        catch {
            $errorString = $_.ToString()
            Write-Warning "Could not retrieve region status for account $($accountId). Proceeding without disabled region check for this account. Error: $($errorString)"
            # Allow script to continue, just won't skip disabled regions for this account
        }
        # --- END Fetch Disabled Regions for Account ---

        # Calculate total services for progress bar within this account
        $servicesInAccount = ($resourceTypes.Values | ForEach-Object { $_.Keys }).Count
        $processedInAccount = 0

        # Process resource types for the current account (with assumed or default credentials)
        foreach ($category in $resourceTypes.Keys) {
            foreach ($resourceType in $resourceTypes[$category].Keys) {
                $cmdlet = $resourceTypes[$category][$resourceType]
                # Determine target regions: Global for S3/CloudFront, specific list otherwise
                $targetRegions = if ($resourceType -in @("AWS::S3::Bucket", "AWS::CloudFront::Distribution")) { 
                    @($GlobalRegion) 
                }
                else { 
                    $regionList # Use the globally defined region list
                }
                
                # Call the updated Get-AWSResources with current account's credentials
                # Pass $currentCredentials (which is null for default context, or the assumed role creds)
                $resourcesFound = Get-AWSResources -Regions $targetRegions -ResourceType $resourceType -Cmdlet $cmdlet -Category $category -Credentials $currentCredentials -ResourceTypeRegionsMap $resourceTypeRegions -DisabledAccountRegions $disabledRegionsForAccount
                
                if ($resourcesFound) {
                    $allResources += $resourcesFound
                }

                $processedInAccount++
                # Update progress based on services within the current account
                $percentComplete = if ($servicesInAccount -gt 0) { [Math]::Round($processedInAccount * 100 / $servicesInAccount) } else { 100 }
                # Use Write-Progress with a specific ID for the inner loop to avoid conflicts if outer loop also uses it
                Write-Progress -Activity "Processing Account $accountId [$accountIndex/$totalAccounts]" -Status "$ResourceType ($processedInAccount/$servicesInAccount)" -PercentComplete $percentComplete -Id 1
            }
        }
        # Complete the progress bar for the account
        Write-Progress -Activity "Processing Account $accountId [$accountIndex/$totalAccounts]" -Completed -Id 1
    }

    if (-not $allResources) {
        Write-Warning "No resources found or processed across all accounts."
        # Decide whether to create empty files or just exit
        # return 
    }

    # Ensure $allResources is an array, even if only one item was added from the ConcurrentBag
    if ($allResources -is [PSCustomObject]) { $allResources = @($allResources) }

    $summaryData = $allResources | Group-Object -Property Category, AccountId | ForEach-Object {
        [PSCustomObject]@{
            Category  = $_.Group[0].Category
            AccountId = $_.Group[0].AccountId
            Count     = $_.Count
        }
    }

    # Sort summary data for consistent output
    $summaryData = $summaryData | Sort-Object AccountId, Category

    try {
        $summaryData | Export-Csv -Path $OutputFile -NoTypeInformation -Encoding UTF8 -ErrorAction Stop
        Write-Host "Resource summary exported to: $OutputFile"
    }
    catch {
        # Explicitly capture error string
        $errorString = $_.ToString()
        Write-Error "Failed to export summary CSV to $($OutputFile): $($errorString)"
    }

    if ($DetailedResults) {
        # Group by Account, ResourceType, Category
        $groupedResourceData = $allResources | Group-Object -Property AccountId, ResourceType, Category | ForEach-Object {
            $group = $_.Group
            [PSCustomObject]@{
                AccountId    = $group[0].AccountId
                ResourceType = $group[0].ResourceType
                Type         = $group[0].Category # Use Category consistently
                Count        = $group.Count # Count items in the group
            }
        }
        
        # Sort detailed data
        $groupedResourceData = $groupedResourceData | Sort-Object AccountId, ResourceType

        # --- Robust Path Construction for Detailed File ---
        # 1. Get the base filename for the detailed report
        $detailedFileName = [System.IO.Path]::GetFileNameWithoutExtension($OutputFile) + "_detailed.csv"
        
        # 2. Determine the target directory from the main OutputFile path
        $outputDir = Split-Path -Path $OutputFile -Parent

        # 3. Construct the full path for the detailed file
        # If $outputDir is empty/null (OutputFile was just a name), use the current location
        # Otherwise, join the directory and filename
        $detailedOutputFullPath = if ([string]::IsNullOrEmpty($outputDir)) {
            Join-Path -Path (Get-Location).Path -ChildPath $detailedFileName
        }
        else {
            Join-Path -Path $outputDir -ChildPath $detailedFileName
        }

        # 4. Ensure the target directory exists *before* trying to export
        # Check if $outputDir is not empty AND the directory doesn't exist
        if (-not [string]::IsNullOrEmpty($outputDir) -and (-not (Test-Path -Path $outputDir -PathType Container))) {
            try {
                New-Item -Path $outputDir -ItemType Directory -Force -ErrorAction Stop | Out-Null
                Write-Verbose "Created directory: $outputDir" -Verbose
            }
            catch {
                $errorString = $_.ToString()
                Write-Warning "Could not create directory '$outputDir' for detailed export: $($errorString)"
                # Optionally skip detailed export if directory creation fails
                # return or continue might be appropriate depending on desired behavior
            }
        }
        # --- End Path Construction ---

        # 5. Try to export the detailed CSV
        try {
            $groupedResourceData | Export-Csv -Path $detailedOutputFullPath -NoTypeInformation -Encoding UTF8 -ErrorAction Stop
            Write-Host "Detailed resource summary exported to: $detailedOutputFullPath"
        }
        catch {
            # Explicitly capture error string
            $errorString = $_.ToString()
            # Write error with the path it *attempted* to use
            Write-Error "Failed to export detailed CSV to '$($detailedOutputFullPath)': $($errorString)"
        }
    }

    # Display summary table only if data exists
    if ($summaryData) {
        Write-Host "`nSummary:"
        $summaryData | Format-Table -AutoSize
    }

    if ($PassThru) {
        Write-Host "`nReturning results as PSObject..."
        # Return detailed results if requested, otherwise summary
        if ($DetailedResults) { 
            return $groupedResourceData 
        }
        else { 
            return $summaryData 
        }
    }
}
catch {
    # Catch errors from the main script body
    # Explicitly capture error details for better reporting
    $errorRecord = $_ # The full error record
    $errorMessage = $errorRecord.Exception.Message
    $invocationInfo = $errorRecord.InvocationInfo
    $scriptStackTrace = $errorRecord.ScriptStackTrace

    Write-Error "An error occurred during script execution."
    Write-Error "Error Message: $($errorMessage)"
    # Display info about the command that failed, if available
    if ($invocationInfo) {
        Write-Error "Failed Command Name: $($invocationInfo.MyCommand.Name)"
        Write-Error "Line Number: $($invocationInfo.ScriptLineNumber)"
        Write-Error "Offset in Line: $($invocationInfo.OffsetInLine)"
        # Display the line where the error occurred
        Write-Error "Line Content: $($invocationInfo.Line)"

    }
    # Display the script stack trace for context
    if ($scriptStackTrace) {
        Write-Error "Script Stack Trace:`n$($scriptStackTrace)"
    }
}