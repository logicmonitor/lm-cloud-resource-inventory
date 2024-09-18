<#
.SYNOPSIS
Counts AWS resources across specified regions and categorizes them.

.DESCRIPTION
This script enumerates AWS resources across one or more regions, categorizes them as IaaS, PaaS, or Non-compute,
and provides a summary count. It also identifies any unsupported resource types.

.PARAMETER Regions
Comma-separated list of AWS regions to process. If not provided, all regions will be processed.

.PARAMETER DetailedResults
Switch to include additional resource details as part of the detailed export.

.PARAMETER PassThru
Switch to pass through export results as a PSObject.

.PARAMETER OutputFile
The name of the CSV file to export the results. Default is "aws_resource_count_output.csv".

.EXAMPLE
.\get_aws_resource_counts.ps1 -Regions "us-east-1,us-west-2" -OutputFile "custom_output.csv"

.EXAMPLE
.\get_aws_resource_counts.ps1 -DetailedResults -PassThru

.NOTES
Requires the AWS.Tools PowerShell modules to be installed and an active AWS connection.
#>

param (
    [Parameter(HelpMessage="Comma-separated list of AWS regions")]
    [string]$Regions,

    [Parameter(HelpMessage="Include full resource details as part of inventory export")]
    [switch]$DetailedResults,

    [Parameter(HelpMessage="Pass through export results as a PSObject")]
    [switch]$PassThru,

    [Parameter(HelpMessage="Output CSV file name")]
    [string]$OutputFile = "aws_resource_count_output.csv",

    [Parameter(HelpMessage="Region to use to query global namespaces such as S3")]
    [string]$GlobalRegion = "us-east-1"
)

# Define regions if not provided
if (-not $Regions) {
    $regionList = @(
        "us-east-1", "us-east-2", "us-west-1", "us-west-2", "eu-central-1", "eu-north-1",
        "eu-south-1", "eu-west-1", "eu-west-2", "eu-west-3", "ap-east-1", "ap-northeast-1",
        "ap-northeast-2", "ap-northeast-3", "ap-south-1", "ap-southeast-1", "ap-southeast-2",
        "ap-southeast-3", "af-south-1", "ca-central-1", "me-south-1", "sa-east-1"
    )
} else {
    $regionList = $Regions -split ',' | ForEach-Object { $_.Trim() }
}

# Define resource types
$nonComputeResourceTypeCmdlets = @{
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
    "AWS::ECS::Cluster" = "Get-ECSClusterList" 
    "AWS::EFS::FileSystem" = "Get-EFSFileSystem"
    "AWS::ElasticBeanstalk::Environment" = "Get-EBEnvironment"
    "AWS::EMR::Cluster" = "Get-EMRClusterList" #Does not support cloud control api
    "AWS::KinesisFirehose::DeliveryStream" = "Get-KINFDeliveryStreamList"
    "AWS::KinesisVideo::Stream" = "Get-KVStreamList"
    "AWS::Kinesis::Stream" = "Get-KINStreamList"
    "AWS::Lambda::Function" = "Get-LMFunctionList"
    "AWS::ElasticLoadBalancing::LoadBalancer" = "Get-ELBLoadBalancer" #Does not support cloud control api
    "AWS::ElasticLoadBalancingV2::LoadBalancer" = "Get-ELB2LoadBalancer"
    "AWS::MediaConnect::Flow" = "Get-EMCNFlowList"
    "AWS::MediaPackage::Channel" = "Get-EMPChannelList"
    "AWS::MediaPackage::PackagingGroup" = "Get-EMPVPackagingGroupList"
    "AWS::Redshift::Cluster" = "Get-RSCluster"
    "AWS::Route53::HealthCheck" = "Get-R53HealthCheckList"
    "AWS::SES::ConfigurationSet" = "Get-SES2ConfigurationSetList"
    "AWS::SNS::Topic" = "Get-SNSTopic"
    "AWS::SQS::Queue" = "Get-SQSQueue"
    "AWS::MSK::Cluster" = "Get-MSKClusterList"
    "AWS::StepFunctions::StateMachine" = "Get-SFNStateMachineList"
}

# Global Resource Types
$globalResourceTypeCmdlets = @{
    "AWS::CloudFront::Distribution" = "Get-CFDistributionList"
    "AWS::S3::Bucket" = "Get-S3Bucket"
}

# IaaS Resources
$iaasResourceTypeCmdlets = @{
    "AWS::EC2::Instance" = "Get-EC2Instance"
}

# PaaS Resources
$paasResourceTypeCmdlets = @{
    "AWS::ECS::Cluster" = "Get-ECSClusterList"
    "AWS::Lambda::Function" = "Get-LMFunctionList"
    "AWS::AppStream::Fleet" = "Get-APSFleetList" #Does not support cloud control api
    "AWS::CloudSearchDomain" = "Get-CSDomainNameList" #Does not support cloud control api
    "AWS::Glue::Job" = "Get-GLUEJobList" #Does not support cloud control api
    "AWS::AmazonMQ::Broker" = "Get-MQBrokerList" #Does not support cloud control api
    "AWS::MSK::Cluster" = "Get-MSKClusterList"
    "AWS::OpenSearchService::Domain" = "Get-OSDomainNameList"
    "AWS::QuickSight::Dashboard" = "Get-QSDashboardList"
    "AWS::QuickSight::Dataset" = "Get-QSDatasetList"
    "AWS::ElastiCache::CacheCluster" = "Get-ECCacheCluster"
    "AWS::FSx::FileSystem" = "Get-FSXFileSystem" #Does not support cloud control api
    "AWS::Bedrock::FoundationModels" = "Get-BDRFoundationModelList" #Does not support cloud control api
    "AWS::Bedrock::CustomModels" = "Get-BDRCustomModelList" #Does not support cloud control api
    "AWS::Redshift::Cluster" = "Get-RSCluster"
    "AWS::RDS::DBInstance" = "Get-RDSDBInstance"
}

# Function to create custom objects
function New-ResourceObject {
    param (
        [string]$Resource,
        [string]$Cmdlet,
        [string]$ResourceType
    )
    
    return [PSCustomObject]@{
        Resource = $Resource
        Cmdlet = $Cmdlet
        ResourceType = $ResourceType
    }
}

function Get-AWSResources {
    param (
        [string[]]$Regions,
        $Resource
    )

    $allResources = @()
    
    foreach ($region in $Regions) {
        Write-Host "Processing $($Resource.Resource) in region: $region"
        
        try {
            $timeout = [TimeSpan]::FromMilliseconds(10000)
            $clientConfig = @{Timeout = $timeout}
            
            $cmdletName = $Resource.Cmdlet
            If($cmdletName -like "*-QS*"){
                $Account = (Get-STSCallerIdentity).Account
                $scriptBlock = [ScriptBlock]::Create("$cmdletName -Region $region -AwsAccountId $Account -ClientConfig `$clientConfig")
            } else {
                $scriptBlock = [ScriptBlock]::Create("$cmdletName -Region $region -ClientConfig `$clientConfig")
            }
            
            $resources = & $scriptBlock
            
            foreach ($entry in $resources) {
                $allResources += [PSCustomObject]@{
                    Region = $region
                    ResourceType = $($Resource.Resource)
                    Category = $($Resource.ResourceType)
                }
            }
        }
        catch {
            if ($_.Exception.Message -like "*is not supported in this region*") {
                Write-Host "Resource type $($Resource.Resource) is not supported in region $region"
            }
            else {
                Write-Host "Error processing $($Resource.Resource) in region $region`: $_"
            }
        }
    }

    return $allResources
}

# Main script execution
$currentIdentity = $null
try {
    # Check AWS connection
    $currentIdentity = Get-STSCallerIdentity
    Write-Host "Connected to AWS as: $($currentIdentity.Arn)"
}
catch {
    Write-Error "Not connected to AWS. Please configure and run Initialize-AWSSSOConfiguration before running this script."
    exit
}

# Combine all hashtables
$allResourcesTypeCmdlets = @{}
$allResources = @()

$nonComputeResourceTypeCmdlets.GetEnumerator() | ForEach-Object { $allResourcesTypeCmdlets[$_.Key] = @{Cmdlet = $_.Value; Type = "Non-Compute"} }
$globalResourceTypeCmdlets.GetEnumerator() | ForEach-Object { $allResourcesTypeCmdlets[$_.Key] = @{Cmdlet = $_.Value; Type = "Non-Compute"} }
$iaasResourceTypeCmdlets.GetEnumerator() | ForEach-Object { $allResourcesTypeCmdlets[$_.Key] = @{Cmdlet = $_.Value; Type = "IaaS"} }
$paasResourceTypeCmdlets.GetEnumerator() | ForEach-Object { $allResourcesTypeCmdlets[$_.Key] = @{Cmdlet = $_.Value; Type = "PaaS"} }

# Create array of custom objects
$resourceObjects = $allResourcesTypeCmdlets.GetEnumerator() | ForEach-Object {
    New-ResourceObject -Resource $_.Key -Cmdlet $_.Value.Cmdlet -ResourceType $_.Value.Type
}

$totalServices = ($resourceObjects | Measure-Object).Count
$processedCount = 0

# Process resources
foreach ($resource in $resourceObjects) {
    if($resource.Resource -like "*S3*" -or $resource.Resource -like "*CloudFront*"){
        $resources = Get-AWSResources -Regions "$GlobalRegion" -Resource $resource
    } else{
        $resources = Get-AWSResources -Regions $regionList -Resource $resource
    }
    $allResources += $resources
    $processedCount++
    Write-Progress -Activity "Processing AWS Resources" -Status "$([Math]::Round($processedCount * 100 / $totalServices))% Complete" -PercentComplete ($processedCount * 100 / $totalServices)
}

# Group the data by Category and calculate the count
$summaryData = $allResources | Group-Object -Property Category | ForEach-Object {
    [PSCustomObject]@{
        Category = $_.Name
        Count = $_.Count
    }
}

# Ensure all categories are represented, even if they have a count of 0
$allCategories = @('IaaS', 'PaaS', 'Non-Compute')
$finalSummaryData = $allCategories | ForEach-Object {
    $category = $_
    $existingEntry = $summaryData | Where-Object { $_.Category -eq $category }
    if ($existingEntry) {
        $existingEntry
    } else {
        [PSCustomObject]@{
            Category = $category
            Count = 0
        }
    }
}

$finalSummaryData | Export-Csv -Path $OutputFile -NoTypeInformation
Write-Host "Resource summary exported to: $OutputFile"

if ($DetailedResults) {
    # Group the data by ResourceType and calculate the sums
    $groupedResourceData = $allResources | Group-Object -Property ResourceType | ForEach-Object {
        $resourceType = $_.Name
        $group = $_.Group

        [PSCustomObject]@{
            ResourceType = $resourceType
            IaaS = ($group | Where-Object { $_.Category -eq 'IaaS' } | Measure-Object).Count
            PaaS = ($group | Where-Object { $_.Category -eq 'PaaS' } | Measure-Object).Count
            NonCompute = ($group | Where-Object { $_.Category -eq 'Non-Compute' } | Measure-Object).Count
        }
    }

    $detailedOutputFile = [System.IO.Path]::GetFileNameWithoutExtension($OutputFile) + "_detailed.csv"
    $groupedResourceData | Export-Csv -Path $detailedOutputFile -NoTypeInformation
    Write-Host "Detailed resource summary exported to: $detailedOutputFile"
}

# Display results
$finalSummaryData | Format-Table -AutoSize

# Return PSObject if specified
if ($PassThru){
    if($DetailedResults){
        return $groupedResourceData
    } else {
        return $finalSummaryData
    }
}