#!/bin/bash

#############
# VARIABLES #
#############

# Define the datasource dictionary as an associative array based
# on information from JIRA DEV-133899
declare -A charged_datasource_dict=(
  ["microsoft.analysisservices/servers"]="PaaS"
  ["microsoft.web/sites"]="PaaS"
  ["microsoft.datafactory/factories"]="PaaS"
  ["microsoft.hdinsight/clusters"]="PaaS"
  ["microsoft.dbformariadb/servers"]="PaaS"
  ["microsoft.sql/servers"]="PaaS"
  ["microsoft.dbforpostgresql/flexibleservers"]="PaaS"
  ["microsoft.dbforpostgresql/servers"]="PaaS"
  ["microsoft.sql/managedinstances"]="PaaS"
  ["microsoft.cache/redis"]="PaaS"
  ["microsoft.desktopvirtualization/hostpools"]="PaaS"
  ["microsoft.compute/virtualmachines"]="IaaS"
  ["microsoft.compute/virtualmachinescalesets/virtualmachines"]="IaaS"
)

declare -A no_charged_datasource_dict=(
  ["microsoft.apimanagement/service"]="Non-compute"
  ["microsoft.network/applicationgateways"]="Non-compute"
  ["microsoft.web/hostingenvironments"]="Non-compute"
  ["microsoft.web/serverfarms"]="Non-compute"
  ["microsoft.recoveryservices/vaults"]="Non-compute"
  ["microsoft.recoveryservices/vaults/backupfabrics/protectioncontainers/protecteditems"]="Non-compute"
  ["microsoft.recoveryservices/vaults/backupjobs"]="Non-compute"
  ["microsoft.batch/batchaccounts"]="Non-compute"
  ["microsoft.search/searchservices"]="Non-compute"
  ["microsoft.cognitiveservices/accounts"]="Non-compute"
  ["microsoft.documentdb/databaseaccounts"]="Non-compute"
  ["microsoft.eventgrid/topics"]="Non-compute"
  ["microsoft.eventhub/namespaces"]="Non-compute"
  ["microsoft.network/expressroutecircuits"]="ds_expresNon-computesroutecircuits_azure"
  ["microsoft.network/azurefirewalls"]="Non-compute"
  ["microsoft.network/frontdoors"]="Non-compute"
  ["microsoft.devices/iothubs"]="Non-compute"
  ["microsoft.keyvault/vaults"]="Non-compute"
  ["microsoft.network/loadbalancers"]="Non-compute"
  ["microsoft.logic/workflows"]="Non-compute"
  ["microsoft.machinelearningservices/workspaces"]="Non-compute"
  ["microsoft.notificationhubs/namespaces"]="Non-compute"
  ["microsoft.relay/namespaces"]="Non-compute"
  ["microsoft.servicebus/namespaces"]="Non-compute"
  ["microsoft.operationalinsights/workspaces"]="Non-compute"
  ["microsoft.servicefabricmesh/applications"]="Non-compute"
  ["microsoft.signalrservice/signalr"]="Non-compute"
  ["microsoft.synapse/workspaces"]="Non-compute"
  ["microsoft.compute/virtualmachines"]="Non-compute"
  ["microsoft.network/virtualnetworkgateways"]="Non-compute"
  ["microsoft.automation/automationaccounts"]="Non-compute"
  ["microsoft.network/virtualhubs"]="Non-compute"
  ["microsoft.network/vpngateways"]="Non-compute"
  ["microsoft.cdn/profiles"]="Non-compute"
  ["microsoft.netapp/netappaccounts"]="Non-compute"
  ["microsoft.network/networkinterfaces"]="Non-compute"
  ["microsoft.insights/components"]="Non-compute"
  ["microsoft.datalakeanalytics/accounts"]="Non-compute"
  ["microsoft.datalakestore/accounts"]="Non-compute"
  ["microsoft.storage/storageaccounts/file"]="Non-compute"
  ["microsoft.storage/storageaccounts/blob"]="Non-compute"
  ["microsoft.storage/storageaccounts/table"]="Non-compute"
  ["microsoft.storage/storageaccounts/queue"]="Non-compute"
  ["microsoft.storage/storageaccounts"]="Non-compute"
  ["microsoft.network/publicipaddresses"]="Non-compute"
  ["microsoft.network/trafficmanagerprofiles"]="Non-compute"
  ["microsoft.streamanalytics/streamingjobs"]="Non-compute"
  ["microsoft.dbformysql/flexibleservers"]="Non-compute"
  ["microsoft.dbforpostgresql/servergroupsv2"]="Non-compute"
  ["microsoft.compute/virtualmachinescalesets"]="Non-compute"
)

declare -A service_count=(
  ["IaaS"]=0
  ["PaaS"]=0
  ["Non-compute"]=0
  ["Non-compute"]=0
)

azure_resources_csv_file="azure_resources_csv_file"

#############
# FUNCTIONS #
#############

show_help() {
    echo "Usage: $0 [-h] [output_file_name]"
    echo "  -h                Display this help message."
    echo "  output_file_name  Output file name. If not provided, the default name"
    echo "                    will be used - azure_resource_count_output.csv."
    exit 0
}

# Function to calculate resources types
count_resources() {
  local az_graph_output="$1"
  local type="$2"

  # Read input using a for loop
  declare -A resources
  IFS=$'\n' read -r -d '' -a lines <<< "$az_graph_output"
  for line in "${lines[@]}"; do
    # Extract the first column value
    value=$(echo "$line" | cut -f1)
    resources[$value]=$((resources[$value]+1))
  done

  # Print the unique values along with their counts
  for value in "${!resources[@]}"; do
    count="${resources[$value]}"
    echo "$value,$type,$count" >> $azure_resources_csv_file
  done

  unset resources
}

to_lowercase() {
  local input=$1
  local output=""

  for (( i=0; i<${#input}; i++ )); do
    local char="${input:i:1}"
    local lowercase_char="${char,,}"
    output+="$lowercase_char"
  done
  echo "$output"
}

#############
#    MAIN   #
#############

# Check if the -h option is provided
if [ "$1" == "-h" ] || [ "$1" == "-help" ]; then
    show_help
fi

# Check if output file is provided
if [ -z "$1" ]; then
    output_csv_file="azure_resource_count_output.csv"  # Use the default value
else
    output_csv_file="$1"  # Use customer provided name
fi

if [ -f "$azure_resources_csv_file" ]; then
    rm -f "$azure_resources_csv_file"
fi

# Loop through all resource groups in the subscription
for rg in $(az group list --query "[].name" -o tsv)
do
  echo "Calculating resources for resource group: $rg"

  # Declare an associative array to store the count of each service type
  declare -A resource_count

  # Get the list of resources in each resource group and their types
  resource_types=$(az resource list -g $rg --query "[].type" -o tsv)

  # Loop through each resource type in the resource group
  for resource_type in $resource_types
  do
    # Increment the count for the specific resource type
    resource_count[$resource_type]=$((resource_count[$resource_type]+1))
  done

  # Print the count of each service type as CSV
  for key in "${!resource_count[@]}"; do
    echo "$rg,$key,${resource_count[$key]}" >> $azure_resources_csv_file
  done
  unset resource_count
done


# Retrieve the list of VMSS instances
vmss_list=$(az vmss list --query "[].id" -o tsv)

# Loop through each VMSS instance
if [ -n "$vmss_list" ]; then
  while IFS= read -r vmss_name
  do
    # Retrieve the list of virtual machines in the VMSS
    name=$(echo "$vmss_name" | sed 's/.*\///')
    resource_group=$(echo "$vmss_name" | sed 's/.*\/resourceGroups\/\([^/]*\).*/\1/')
    vm_list=$(az vmss list-instances --name "$name" --resource-group "$resource_group" --query "[].{ResourceGroup: resourceGroup, Type: type}" -o tsv)
    count_resources "$vm_list" "microsoft.compute/virtualmachinescalesets/virtualmachines"
  done <<< "$vmss_list"
fi

# Calculate number of PaaS, IaaS, etc. services
while IFS=, read -r resource_group_name resource_type count; do
  # Check if the resource type has a corresponding LogicMonitor datasource
  lowercase_resource_type=$(to_lowercase "$resource_type")
  if [ -n "${charged_datasource_dict[$lowercase_resource_type]}" ]; then
    type="${charged_datasource_dict[$lowercase_resource_type]}"
    service_count[$type]=$((service_count[$type]+$count))
  elif [ -n "${no_charged_datasource_dict[$lowercase_resource_type]}" ]; then
    service_count["Non-compute"]=$((service_count["Non-compute"]+$count))
  else
    service_count["Unsupported"]=$((service_count["Unsupported"]+$count))
  fi
done < "$azure_resources_csv_file"

# Create file with results
echo "Category,Number" >> "$output_csv_file"
for key in "${!service_count[@]}"; do
    if [ $key != "Unsupported" ]; then
      value="${service_count[$key]}"
      echo "$key,$value" >> "$output_csv_file"
    fi
  done


echo "Output saved to $output_csv_file"

if [ -f "$azure_resources_csv_file" ]; then
    rm -f "$azure_resources_csv_file"
fi