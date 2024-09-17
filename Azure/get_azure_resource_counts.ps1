<#
.SYNOPSIS
Counts Azure resources across specified subscriptions and categorizes them.

.DESCRIPTION
This script enumerates Azure resources across one or more subscriptions, categorizes them as IaaS, PaaS, or Non-compute,
and provides a summary count. It also identifies any unsupported resource types.

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
.\Count-AzureResources.ps1 -Subscriptions "Sub1,Sub2" -OutputFile "custom_output.csv"

.EXAMPLE
.\Count-AzureResources.ps1 -ResourceGroups "RG1,RG2" -DetailedResults -PassThru

.NOTES
Requires the Az PowerShell module to be installed and an active Azure connection.
#>

param (
    [Parameter(HelpMessage="Comma-separated list of subscription names")]
    [string]$Subscriptions,

    [Parameter(HelpMessage="Comma-separated list of resource groups")]
    [string]$ResourceGroups,

    [Parameter(HelpMessage="Include full resource details as part of inventory export")]
    [switch]$DetailedResults,

    [Parameter(HelpMessage="Pass through export results as a PSObject")]
    [switch]$PassThru,

    [Parameter(HelpMessage="Output CSV file name")]
    [string]$OutputFile = "azure_resource_count_output.csv"
)

function Get-ResourceCategory {
    param (
        [string]$resourceType
    )

    $charged_datasource_dict = @{
        "microsoft.analysisservices/servers" = "PaaS"
        "microsoft.web/sites" = "PaaS"
        "microsoft.web/serverfarms" = "PaaS" #previously missing
        "microsoft.web/hostingenvironments" = "PaaS" #previously missing
        "microsoft.datafactory/factories" = "PaaS"
        "microsoft.hdinsight/clusters" = "PaaS"
        "microsoft.dbformariadb/servers" = "PaaS"
        "microsoft.sql/managedinstances" = "PaaS"
        "microsoft.sql/servers/databases" = "PaaS" #previously missing
        "microsoft.sql/servers/elasticpools" = "PaaS" #previously missing
        "microsoft.dbforpostgresql/flexibleservers" = "PaaS"
        "microsoft.dbforpostgresql/servers" = "PaaS"
        "microsoft.dbforpostgresql/servergroupsv2" = "PaaS" #previously listed as Non-Compute
        "microsoft.dbformysql/servers" = "PaaS" #previously missing
        "microsoft.dbformysql/flexibleservers" = "PaaS" #previously missing
        "microsoft.botservice/botservices" = "PaaS" #previously missing
        "microsoft.powerbidedicated/capacities" = "PaaS" #previously missing
        "microsoft.cache/redis" = "PaaS"
        "microsoft.desktopvirtualization/hostpools" = "PaaS"
        "microsoft.compute/virtualmachines" = "IaaS"
        "microsoft.compute/virtualmachinescalesets/virtualmachines" = "IaaS"
    }

    $no_charged_datasource_dict = @{
        "microsoft.apimanagement/service" = "Non-compute"
        "microsoft.network/applicationgateways" = "Non-compute"
        "microsoft.network/virtualwans" = "Non-compute" #previously missin
        "microsoft.recoveryservices/vaults" = "Non-compute"
        "microsoft.recoveryservices/vaults/backupfabrics/protectioncontainers/protecteditems" = "Non-compute"
        "microsoft.recoveryservices/vaults/backupjobs" = "Non-compute"
        "microsoft.batch/batchaccounts" = "Non-compute"
        "microsoft.search/searchservices" = "Non-compute"
        "microsoft.cognitiveservices/accounts" = "Non-compute"
        "microsoft.documentdb/databaseaccounts" = "Non-compute"
        "microsoft.eventgrid/topics" = "Non-compute"
        "microsoft.eventhub/namespaces" = "Non-compute"
        "microsoft.network/expressroutecircuits" = "Non-compute"
        "microsoft.network/azurefirewalls" = "Non-compute"
        "microsoft.network/frontdoors" = "Non-compute"
        "microsoft.devices/iothubs" = "Non-compute"
        "microsoft.keyvault/vaults" = "Non-compute"
        "microsoft.network/loadbalancers" = "Non-compute"
        "microsoft.logic/workflows" = "Non-compute"
        "microsoft.machinelearningservices/workspaces" = "Non-compute"
        "microsoft.notificationhubs/namespaces" = "Non-compute"
        "microsoft.relay/namespaces" = "Non-compute"
        "microsoft.servicebus/namespaces" = "Non-compute"
        "microsoft.operationalinsights/workspaces" = "Non-compute"
        "microsoft.servicefabricmesh/applications" = "Non-compute"
        "microsoft.signalrservice/signalr" = "Non-compute"
        "microsoft.synapse/workspaces" = "Non-compute"
        "microsoft.network/virtualnetworkgateways" = "Non-compute"
        "microsoft.network/virtualnetworks" = "Non-compute" #previously missing
        "microsoft.automation/automationaccounts" = "Non-compute"
        "microsoft.network/virtualhubs" = "Non-compute"
        "microsoft.network/vpngateways" = "Non-compute"
        "microsoft.network/natgateways" = "Non-compute" #previously missing
        "microsoft.cdn/profiles" = "Non-compute"
        "microsoft.netapp/netappaccounts" = "Non-compute"
        "microsoft.network/networkinterfaces" = "Non-compute"
        "microsoft.insights/components" = "Non-compute"
        "microsoft.datalakeanalytics/accounts" = "Non-compute"
        "microsoft.datalakestore/accounts" = "Non-compute"
        "microsoft.storage/storageaccounts/file" = "Non-compute"
        "microsoft.storage/storageaccounts/blob" = "Non-compute"
        "microsoft.storage/storageaccounts/table" = "Non-compute"
        "microsoft.storage/storageaccounts/queue" = "Non-compute"
        "microsoft.storage/storageaccounts" = "Non-compute"
        "microsoft.network/publicipaddresses" = "Non-compute"
        "microsoft.network/trafficmanagerprofiles" = "Non-compute"
        "microsoft.streamanalytics/streamingjobs" = "Non-compute"
    }

    $lowercaseType = $resourceType.ToLower()
    if ($charged_datasource_dict.ContainsKey($lowercaseType)) {
        return $charged_datasource_dict[$lowercaseType]
    } elseif ($no_charged_datasource_dict.ContainsKey($lowercaseType)) {
        return $no_charged_datasource_dict[$lowercaseType]
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

        $resources = Get-AzResource
        $vmssInstances = Get-AzVmssVM -ErrorAction SilentlyContinue

        # Check if $ResourceGroups is provided as a parameter
        if ($ResourceGroups) {
            $ResourceGroupList = $ResourceGroups -split ',' | ForEach-Object { $_.Trim() }
            $subscriptionResources = $resources | Where-Object { $ResourceGroupList -contains $_.ResourceGroupName }
        } else {
            # If not provided, include all resource groups
            $subscriptionResources = $resources
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
if ($DetailedResults){
    # Export results to CSV
    $DetailOutputFile = [System.IO.Path]::GetFileNameWithoutExtension($OutputFile).ToString() + "_detailed.csv"
    $allResources | Select-Object Subscription,ResourceGroup,ResourceName,Location,Category | Export-Csv -Path $DetailOutputFile -NoTypeInformation

    Write-Host "Resource detailed inventory exported to: $DetailOutputFile"
} 

$summarizedResources = $allResources | 
    Group-Object Category | 
    Where-Object { $_.Name -ne "Unsupported" } |
    Select-Object @{N='Category';E={$_.Name}}, @{N='Count';E={($_.Group | Measure-Object Count -Sum).Sum}}

# Export results to CSV
$summarizedResources | Export-Csv -Path $OutputFile -NoTypeInformation
Write-Host "Resource summary exported to: $OutputFile"

# Display results
$summarizedResources | Format-Table -AutoSize


# Display unsupported resource types
$unsupportedTypes = $allResources | 
    Where-Object { $_.Category -eq "Unsupported" } | 
    Select-Object ResourceType -Unique

if ($unsupportedTypes) {
    Write-Host "Unsupported resource types found:"
    $unsupportedTypes | ForEach-Object { Write-Host " - $($_.ResourceType)" }
}

# Return PSObject if specified
if ($PassThru){
    return $($allResources | Select-Object Subscription,ResourceGroup,ResourceName,Location,Category)
}