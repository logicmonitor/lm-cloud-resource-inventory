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
[CmdletBinding(DefaultParameterSetName='Default')]
param (
    [Parameter(HelpMessage="Comma-separated list of AWS regions", ParameterSetName = 'Default')]
    [Parameter(ParameterSetName = 'OU')]
    [string]$Regions,

    [Parameter(HelpMessage="Include full resource details as part of inventory export", ParameterSetName = 'Default')]
    [Parameter(ParameterSetName = 'OU')]
    [switch]$DetailedResults,

    [Parameter(HelpMessage="Pass through export results as a PSObject", ParameterSetName = 'Default')]
    [Parameter(ParameterSetName = 'OU')]
    [switch]$PassThru,

    [Parameter(HelpMessage="Output CSV file name", ParameterSetName = 'Default')]
    [Parameter(ParameterSetName = 'OU')]
    [string]$OutputFile = "aws_resource_count_output.csv",

    [Parameter(HelpMessage="Region to use to query global namespaces such as S3", ParameterSetName = 'Default')]
    [Parameter(ParameterSetName = 'OU')]
    [string]$GlobalRegion = "us-east-1",

    [Parameter(Mandatory=$true, HelpMessage="AWS Organizations OU ID", ParameterSetName = 'OU')]
    [string]$OrganizationalUnitId,

    [Parameter(Mandatory=$true, HelpMessage="IAM Role to assume in member accounts", ParameterSetName = 'OU')]
    [string]$AssumeRole
)

# Define resource types and their corresponding cmdlets
$resourceTypes = @{
    "Non-Compute" = @{
        "AWS::ApiGateway::RestApi" = "Get-AGRestApiList"
        "AWS::ApiGatewayV2::Api" = "Get-AG2ApiList"
        "AWS::Athena::WorkGroup" = "Get-ATHWorkGroupList"
        "AWS::Backup::BackupVault" = "Get-BAKBackupVaultList"
        "AWS::DocDBElastic::Cluster" = "Get-DOCDBCluster"
        "AWS::DynamoDB::Table" = "Get-DDBTableList"
        "AWS::EC2::NatGateway" = "Get-EC2NatGateway"
        "AWS::EC2::TransitGatewayAttachment" = "Get-EC2TransitGatewayAttachment"
        "AWS::EC2::TransitGateway" = "Get-EC2TransitGateway"
        "AWS::EC2::VPNConnection" = "Get-EC2VpnConnection"
        "AWS::EC2::Volume" = "Get-EC2Volume"
        "AWS::EFS::FileSystem" = "Get-EFSFileSystem"
        "AWS::ElasticBeanstalk::Environment" = "Get-EBEnvironment"
        "AWS::EMR::Cluster" = "Get-EMRClusterList"
        "AWS::KinesisFirehose::DeliveryStream" = "Get-KINFDeliveryStreamList"
        "AWS::KinesisVideo::Stream" = "Get-KVStreamList"
        "AWS::Kinesis::Stream" = "Get-KINStreamList"
        "AWS::ElasticLoadBalancing::LoadBalancer" = "Get-ELBLoadBalancer"
        "AWS::ElasticLoadBalancingV2::LoadBalancer" = "Get-ELB2LoadBalancer"
        "AWS::MediaConnect::Flow" = "Get-EMCNFlowList"
        "AWS::MediaPackage::Channel" = "Get-EMPChannelList"
        "AWS::MediaPackage::PackagingGroup" = "Get-EMPVPackagingGroupList"
        "AWS::Route53::HealthCheck" = "Get-R53HealthCheckList"
        "AWS::SES::ConfigurationSet" = "Get-SES2ConfigurationSetList"
        "AWS::SNS::Topic" = "Get-SNSTopic"
        "AWS::SQS::Queue" = "Get-SQSQueue"
        "AWS::StepFunctions::StateMachine" = "Get-SFNStateMachineList"
        "AWS::CloudFront::Distribution" = "Get-CFDistributionList"
        "AWS::S3::Bucket" = "Get-S3Bucket"
    }
    "IaaS" = @{
        "AWS::EC2::Instance" = "Get-EC2Instance"
    }
    "PaaS" = @{
        "AWS::ECS::Cluster" = "Get-ECSClusterList"
        "AWS::Lambda::Function" = "Get-LMFunctionList"
        "AWS::AppStream::Fleet" = "Get-APSFleetList"
        "AWS::CloudSearchDomain" = "Get-CSDomainNameList"
        "AWS::Glue::Job" = "Get-GLUEJobList"
        "AWS::AmazonMQ::Broker" = "Get-MQBrokerList"
        "AWS::MSK::Cluster" = "Get-MSKClusterList"
        "AWS::OpenSearchService::Domain" = "Get-OSDomainNameList"
        "AWS::QuickSight::Dashboard" = "Get-QSDashboardList"
        "AWS::QuickSight::Dataset" = "Get-QSDatasetList"
        "AWS::ElastiCache::CacheCluster" = "Get-ECCacheCluster"
        "AWS::FSx::FileSystem" = "Get-FSXFileSystem"
        "AWS::Bedrock::FoundationModels" = "Get-BDRFoundationModelList"
        "AWS::Bedrock::CustomModels" = "Get-BDRCustomModelList"
        "AWS::Redshift::Cluster" = "Get-RSCluster"
        "AWS::RDS::DBInstance" = "Get-RDSDBInstance"
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
    
    $roleArn = "arn:aws:iam::${AccountId}:role/${RoleName}"
    $assumedRole = Use-STSRole -RoleArn $roleArn -RoleSessionName "ResourceInventorySession"
    
    return $assumedRole.Credentials
}

function Get-AWSResources {
    param (
        [string[]]$Regions,
        [string]$ResourceType,
        [string]$Cmdlet,
        [string]$Category,
        [object]$Credentials
    )

    $allResources = @()
    $timeout = [TimeSpan]::FromMilliseconds(10000)
    $clientConfig = @{
        Timeout = $timeout
    }
    $Account = (Get-STSCallerIdentity -Credential $Credentials).Account
    foreach ($region in $Regions) {
        Write-Debug "Processing $ResourceType in region: $region"
        try {
            $scriptBlock = if ($Cmdlet -like "*-QS*") {
                if ($Credentials){
                    [ScriptBlock]::Create("$Cmdlet -Region `$region -AwsAccountId `$Account -ClientConfig `$clientConfig -AccessKey $($Credentials.AccessKeyId) -SecretKey $($Credentials.SecretAccessKey) -SessionToken $($Credentials.SessionToken)")
                } else {
                    [ScriptBlock]::Create("$Cmdlet -Region `$region -AwsAccountId `$Account -ClientConfig `$clientConfig")
                }
            } else {
                if ($Credentials) {
                    [ScriptBlock]::Create("$Cmdlet -Region `$region -ClientConfig `$clientConfig -AccessKey $($Credentials.AccessKeyId) -SecretKey $($Credentials.SecretAccessKey) -SessionToken $($Credentials.SessionToken)")
                } else {
                    [ScriptBlock]::Create("$Cmdlet -Region `$region -ClientConfig `$clientConfig")
                }
            }
            
            $resources = & $scriptBlock
            $allResources += $resources | ForEach-Object {
                [PSCustomObject]@{
                    Region = $region
                    ResourceType = $ResourceType
                    Category = $Category
                    AccountId = $Account
                }
            }
        } catch {
            if ($_.Exception.Message -notlike "*is not supported in this region*" -or $_.Exception.Message -notlike "*Name or service not known*") {
                Write-Warning "Error processing $ResourceType in region $region`: $_"
            }
        }
    }
    return $allResources
}

# Main script execution
try {
    # Check AWS connection
    $currentIdentity = Get-STSCallerIdentity -ErrorAction Stop
    if (-not $currentIdentity) {
        throw "Failed to retrieve AWS identity. Please ensure you're connected to AWS."
    }
    Write-Host "Connected to AWS as: $($currentIdentity.Arn)"

    # Get accounts in the specified OU
    if ($OrganizationalUnitId -and $AssumeRole){
        $accounts = Get-ORGAccountForParent -ParentId $OrganizationalUnitId
        Write-Host "Found $(($accounts | Measure-Object).Count) accounts in the specified OU."
    
        $allResources = @()
        $totalServices = ($resourceTypes.Values | ForEach-Object { $_.Keys }).Count * $($accounts | Measure-Object).Count
        $processedCount = 0
    
        foreach ($account in $accounts) {
            Write-Host "Processing account: $($account.Id)"
            try {
                $assumedCredentials = Invoke-AssumeRole -AccountId $account.Id -RoleName $AssumeRole
    
                foreach ($category in $resourceTypes.Keys) {
                    foreach ($resourceType in $resourceTypes[$category].Keys) {
                        $cmdlet = $resourceTypes[$category][$resourceType]
                        $targetRegions = if ($resourceType -in @("AWS::S3::Bucket", "AWS::CloudFront::Distribution")) { @($GlobalRegion) } else { $regionList }
                        $allResources += Get-AWSResources -Regions $targetRegions -ResourceType $resourceType -Cmdlet $cmdlet -Category $category -Credentials $assumedCredentials
                        $processedCount++
                        Write-Progress -Activity "Processing AWS Resources" -Status "$([Math]::Round($processedCount * 100 / $totalServices))% Complete" -PercentComplete ($processedCount * 100 / $totalServices)
                    }
                }
            } catch {
                Write-Error "Error unable to process account $($account.Id): $_"
            }
        }        
    } else {
        $allResources = @()
        $totalServices = ($resourceTypes.Values | ForEach-Object { $_.Keys }).Count
        $processedCount = 0
    
        foreach ($category in $resourceTypes.Keys) {
            foreach ($resourceType in $resourceTypes[$category].Keys) {
                $cmdlet = $resourceTypes[$category][$resourceType]
                $targetRegions = if ($resourceType -in @("AWS::S3::Bucket", "AWS::CloudFront::Distribution")) { @($GlobalRegion) } else { $regionList }
                $allResources += Get-AWSResources -Regions $targetRegions -ResourceType $resourceType -Cmdlet $cmdlet -Category $category
                $processedCount++
                Write-Progress -Activity "Processing AWS Resources" -Status "$([Math]::Round($processedCount * 100 / $totalServices))% Complete" -PercentComplete ($processedCount * 100 / $totalServices)
            }
        }
    }


    $summaryData = $allResources | Group-Object -Property Category, AccountId | ForEach-Object {
        [PSCustomObject]@{
            Category = $_.Group[0].Category
            AccountId = $_.Group[0].AccountId
            Count = $_.Count
        }
    }

    $summaryData | Export-Csv -Path $OutputFile -NoTypeInformation
    Write-Host "Resource summary exported to: $OutputFile"

    if ($DetailedResults) {
        $groupedResourceData = $allResources | Group-Object -Property ResourceType, AccountId | ForEach-Object {
            $group = $_.Group
            [PSCustomObject]@{
                AccountId = $group[0].AccountId
                ResourceType = $group[0].ResourceType
                Type = $group[0].Category
                Count = ($group | Measure-Object).Count
            }
        }

        $detailedOutputFile = [System.IO.Path]::GetFileNameWithoutExtension($OutputFile) + "_detailed.csv"
        $groupedResourceData | Export-Csv -Path $detailedOutputFile -NoTypeInformation
        Write-Host "Detailed resource summary exported to: $detailedOutputFile"
    }

    $summaryData | Format-Table -AutoSize

    if ($PassThru) {
        if ($DetailedResults) { $groupedResourceData } else { $summaryData }
    }
} catch {
    Write-Error "Error: $_"
}