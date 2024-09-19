<#
.SYNOPSIS
This solution is provided by LogicMonitor in order to collect cloud resource counts within an Azure environment, for LogicMonitor licensing.
.DESCRIPTION
This script performs the following tasks:
1. Enumerates Azure resources across specified subscriptions
2. Categorizes each resource as IaaS, PaaS, or Non-compute
3. Provides a summary count of resources in each category
4. Identifies any unsupported resource types

It offers flexibility in scope, allowing users to focus on specific subscriptions or 
resource groups, and delivers a comprehensive overview of cloud resource distribution.

.PARAMETER Subscriptions
Comma-separated list of subscription names to process. If not provided, all accessible subscriptions will be processed.

.PARAMETER ResourceGroups
Comma-separated list of resource groups to process. If not provided, all resource groups in the specified subscriptions will be processed.

.PARAMETER DetailedResults
Switch to include full resource details as part of the inventory export.

.PARAMETER PassThru
Switch to pass through export results as a PSObject.

.PARAMETER OutputFile
The name of the CSV file to export the results. Default is "azure_resource_count_output.csv".

.EXAMPLE
.\get_azure_resource_counts.ps1 -Subscriptions "Sub1,Sub2" -OutputFile "custom_output.csv"

.EXAMPLE
.\get_azure_resource_counts.ps1 -ResourceGroups "RG1,RG2" -DetailedResults -PassThru

.NOTES
Requires the Az PowerShell module to be installed and an active Azure connection.
#>

param (
    [Parameter(HelpMessage="Comma-separated list of subscription names to include, by default all is included")]
    [string]$Subscriptions,

    [Parameter(HelpMessage="Comma-separated list of resource groups to include, by default all is included")]
    [string]$ResourceGroups,

    [Parameter(HelpMessage="Include full resource details as part of inventory export")]
    [switch]$DetailedResults,

    [Parameter(HelpMessage="Pass through export results as a PSObject")]
    [switch]$PassThru,

    [Parameter(HelpMessage="Include list of unsupported resource types in console output")]
    [switch]$ShowUnsupportedResources,

    [Parameter(HelpMessage="Output CSV file name")]
    [string]$OutputFile = "azure_resource_count_output.csv"
)

function Get-ResourceCategory {
    param (
        [string]$resourceType
    )

    $resourceTypes = @{
        "microsoft.analysisservices/servers" = "PaaS"
        "microsoft.apimanagement/service" = "Non-Compute"
        "microsoft.automation/automationaccounts" = "Non-Compute"
        "microsoft.batch/batchaccounts" = "Non-Compute"
        "microsoft.botservice/botservices" = "PaaS"
        "microsoft.cache/redis" = "PaaS"
        "microsoft.cache/redisenterprise" = "PaaS"
        "microsoft.cdn/profiles" = "Non-Compute"
        "microsoft.cognitiveservices/accounts" = "Non-Compute"
        "microsoft.compute/disks" = "Non-Compute"
        "microsoft.compute/virtualmachines" = "IaaS"
        "microsoft.compute/virtualmachinescalesets" = "Non-Compute"
        "microsoft.compute/virtualmachinescalesets/virtualmachines" = "IaaS"
        "microsoft.containerregistry/registries" = "Non-Compute"
        "microsoft.datafactory/factories" = "PaaS"
        "microsoft.datalakeanalytics/accounts" = "Non-Compute"
        "microsoft.datalakestore/accounts" = "Non-Compute"
        "microsoft.dbformariadb/servers" = "PaaS"
        "microsoft.dbformysql/flexibleservers" = "PaaS"
        "microsoft.dbformysql/servers" = "PaaS"
        "microsoft.dbforpostgresql/flexibleservers" = "PaaS"
        "microsoft.dbforpostgresql/servergroupsv2" = "PaaS"
        "microsoft.dbforpostgresql/servers" = "PaaS"
        "microsoft.desktopvirtualization/hostpools" = "PaaS"
        "microsoft.devices/iothubs" = "Non-Compute"
        "microsoft.documentdb/databaseaccounts" = "Non-Compute"
        "microsoft.eventgrid/topics" = "Non-Compute"
        "microsoft.eventhub/namespaces" = "Non-Compute"
        "microsoft.hdinsight/clusters" = "PaaS"
        "microsoft.insights/components" = "Non-Compute"
        "microsoft.keyvault/vaults" = "Non-Compute"
        "microsoft.logic/workflows" = "Non-Compute"
        "microsoft.machinelearningservices/workspaces" = "Non-Compute"
        "microsoft.netapp/netappaccounts" = "Non-Compute"
        "microsoft.network/applicationgateways" = "Non-Compute"
        "microsoft.network/azurefirewalls" = "Non-Compute"
        "microsoft.network/expressroutecircuits" = "Non-Compute"
        "microsoft.network/frontdoors" = "Non-Compute"
        "microsoft.network/loadbalancers" = "Non-Compute"
        "microsoft.network/natgateways" = "Non-Compute"
        "microsoft.network/networkinterfaces" = "Non-Compute"
        "microsoft.network/publicipaddresses" = "Non-Compute"
        "microsoft.network/trafficmanagerprofiles" = "Non-Compute"
        "microsoft.network/virtualhubs" = "Non-Compute"
        "microsoft.network/virtualnetworkgateways" = "Non-Compute"
        "microsoft.network/virtualnetworks" = "Non-Compute"
        "microsoft.network/vpngateways" = "Non-Compute"
        "microsoft.notificationhubs/namespaces/notificationhubs" = "Non-Compute"
        "microsoft.operationalinsights/workspaces" = "Non-Compute"
        "microsoft.powerbidedicated/capacities" = "PaaS"
        "microsoft.recoveryservices/vaults" = "Non-Compute"
        "microsoft.recoveryservices/vaults/backupfabrics/protectioncontainers/protecteditems" = "Non-Compute"
        "microsoft.recoveryservices/vaults/replicationfabrics/replicationprotectioncontainers/replicationprotecteditems" = "Non-Compute"
        "microsoft.relay/namespaces" = "Non-Compute"
        "microsoft.search/searchservices" = "Non-Compute"
        "microsoft.servicebus/namespaces" = "Non-Compute"
        "microsoft.servicefabricmesh/applications" = "Non-Compute"
        "microsoft.signalrservice/signalr" = "Non-Compute"
        "microsoft.sql/managedinstances" = "PaaS"
        "microsoft.sql/servers/databases" = "PaaS"
        "microsoft.sql/servers/elasticpools" = "PaaS"
        "microsoft.storage/storageaccounts" = "Non-Compute"
        "microsoft.storage/storageaccounts/file" = "Non-compute"
        "microsoft.storage/storageaccounts/blob" = "Non-compute"
        "microsoft.storage/storageaccounts/table" = "Non-compute"
        "microsoft.storage/storageaccounts/queue" = "Non-compute"
        "microsoft.streamanalytics/streamingjobs" = "Non-Compute"
        "microsoft.synapse/workspaces" = "Non-Compute"
        "microsoft.web/hostingenvironments" = "PaaS"
        "microsoft.web/serverfarms" = "PaaS"
        "microsoft.web/sites" = "PaaS"
    }

    $resourceType = $resourceType.ToLower()
    if ($resourceTypes.ContainsKey($resourceType)) {
        return $resourceTypes[$resourceType]
    } else {
        return "Unsupported"
    }
}

function Get-AzureResources {
    param (
        [string[]]$Subscriptions
    )

    $allResources = @()

    foreach ($subscription in $Subscriptions) {
        Write-Host "Processing subscription: $subscription"
        Set-AzContext -Subscription $subscription | Out-Null

        $subscriptionResources = @()
        $vmssInstances = @()

        if ($ResourceGroups) {
            $resourceGroupList = $ResourceGroups -split ',' | ForEach-Object { $_.Trim() }
            foreach ($rg in $resourceGroupList) {
                Write-Host "Processing resource group: $rg"
                $subscriptionResources += Get-AzResource -ResourceGroupName $rg
                $vmssInstances += Get-AzVmssVM -ResourceGroupName $rg -ErrorAction SilentlyContinue
            }
        } else {
            $resourceGroups = (Get-AzResourceGroup | Measure-Object).Count
            Write-Host "Processing all $resourceGroups resource groups in subscription: $subscription"

            $subscriptionResources = Get-AzResource
            $vmssInstances = Get-AzVmssVM -ErrorAction SilentlyContinue

        }

        $subscriptionResources = $subscriptionResources | ForEach-Object {
            [PSCustomObject]@{
                Subscription = $subscription
                ResourceGroup = $_.ResourceGroupName
                ResourceName = $_.ResourceName
                ResourceType = $_.ResourceType
                Location = $_.Location
                Category = Get-ResourceCategory -resourceType $_.ResourceType
                Count = 1
            }
        }

        if ($vmssInstances) {
            $vmssResources = $vmssInstances | ForEach-Object {
                [PSCustomObject]@{
                    Subscription = $subscription
                    ResourceGroup = $_.ResourceGroupName
                    ResourceName = $_.ResourceName
                    ResourceType = $_.ResourceType
                    Location = $_.Location
                    Category = Get-ResourceCategory -resourceType $_.ResourceType
                    Count = 1
                }
            }
            $subscriptionResources += $vmssResources
        }

        $allResources += $subscriptionResources
    }

    return $allResources
}

# Check if an existing context is open, if not prompt for login
function Connect-AzureIfNeeded {
    # Check if there's an existing Azure context
    $context = Get-AzContext -ErrorAction SilentlyContinue

    if (-not $context) {
        Write-Host "No active Azure context found. Prompting for login..."
        try {
            Start-Sleep -Seconds 5
            Connect-AzAccount -ErrorAction Stop | Out-Null
            Write-Host "Successfully connected to Azure."
        }
        catch {
            Write-Error "Failed to connect to Azure: $_"
            exit
        }
    }
    else {
        Write-Host "Using existing Azure context: $($context.Account) - $($context.Subscription.Name)"
    }
}

# Call the function to ensure we're connected
Connect-AzureIfNeeded

# If no subscriptions are provided, get all subscriptions
if (-not $Subscriptions) {
    Write-Host "No subscriptions provided. Getting all subscriptions."
    $subscriptionList = (Get-AzSubscription).Name
} else {
    $subscriptionList = $Subscriptions -split ','
}

Write-Host "Checking $(($subscriptionList | Measure-Object).Count) subscriptions for resources."

# Get all resources
$allResources = Get-AzureResources -Subscriptions $subscriptionList

# Group and summarize resources
if ($DetailedResults) {
    # Export results to CSV
    $detailOutputFile = [System.IO.Path]::GetFileNameWithoutExtension($OutputFile).ToString() + "_detailed.csv"
    
    $detailedResources = $allResources | 
        Where-Object { $_.Category -ne "Unsupported" } |
        Group-Object Subscription, ResourceGroup, ResourceType, Category | 
        ForEach-Object {
            [PSCustomObject]@{
                Subscription = $_.Group[0].Subscription
                ResourceGroup = $_.Group[0].ResourceGroup
                ResourceType = $_.Group[0].ResourceType
                Category = $_.Group[0].Category
                Count = $_.Count
            }
        }
    $detailedResources | Export-Csv -Path $detailOutputFile -NoTypeInformation

    Write-Host "Resource detailed inventory exported to: $detailOutputFile"
} 

$summarizedResources = $allResources | 
    Group-Object Category | 
    Where-Object { $_.Name -ne "Unsupported" } |
    Select-Object @{N='Category';E={$_.Name}}, @{N='Count';E={($_.Group | Measure-Object Count -Sum).Sum}}

# Export results to CSV
$summarizedResources | Export-Csv -Path $OutputFile -NoTypeInformation
Write-Host "Resource summary exported to: $OutputFile"

# Display unsupported resource types
if ($ShowUnsupportedResources) {
    $unsupportedTypes = $allResources | 
        Where-Object { $_.Category -eq "Unsupported" } | 
        Select-Object ResourceType -Unique

    if ($unsupportedTypes) {
        Write-Host "Unsupported resource types found:"
        $unsupportedTypes | ForEach-Object { Write-Host " - $($_.ResourceType)" }
    }
}

# Display results
$summarizedResources | Format-Table -AutoSize | Out-String | Write-Host

# Return PSObject if specified
if ($PassThru) {
    if ($DetailedResults) {
        return $detailedResources
    } else {
        return $summarizedResources
    }
}