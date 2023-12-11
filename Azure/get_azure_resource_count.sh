#!/usr/local/bin/bash

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
  ["microsoft.apimanagement/service"]="PaaS_Non_Charged"
  ["microsoft.network/applicationgateways"]="PaaS_Non_Charged"
  ["microsoft.web/hostingenvironments"]="PaaS_Non_Charged"
  ["microsoft.web/serverfarms"]="PaaS_Non_Charged"
  ["microsoft.recoveryservices/vaults"]="PaaS_Non_Charged"
  ["microsoft.recoveryservices/vaults/backupfabrics/protectioncontainers/protecteditems"]="PaaS_Non_Charged"
  ["microsoft.recoveryservices/vaults/backupjobs"]="PaaS_Non_Charged"
  ["microsoft.batch/batchaccounts"]="PaaS_Non_Charged"
  ["microsoft.search/searchservices"]="PaaS_Non_Charged"
  ["microsoft.cognitiveservices/accounts"]="PaaS_Non_Charged"
  ["microsoft.documentdb/databaseaccounts"]="PaaS_Non_Charged"
  ["microsoft.eventgrid/topics"]="PaaS_Non_Charged"
  ["microsoft.eventhub/namespaces"]="PaaS_Non_Charged"
  ["microsoft.network/expressroutecircuits"]="ds_expresPaaS_Non_Chargedsroutecircuits_azure"
  ["microsoft.network/azurefirewalls"]="PaaS_Non_Charged"
  ["microsoft.network/frontdoors"]="PaaS_Non_Charged"
  ["microsoft.devices/iothubs"]="PaaS_Non_Charged"
  ["microsoft.keyvault/vaults"]="PaaS_Non_Charged"
  ["microsoft.network/loadbalancers"]="PaaS_Non_Charged"
  ["microsoft.logic/workflows"]="PaaS_Non_Charged"
  ["microsoft.machinelearningservices/workspaces"]="PaaS_Non_Charged"
  ["microsoft.notificationhubs/namespaces"]="PaaS_Non_Charged"
  ["microsoft.relay/namespaces"]="PaaS_Non_Charged"
  ["microsoft.servicebus/namespaces"]="PaaS_Non_Charged"
  ["microsoft.operationalinsights/workspaces"]="PaaS_Non_Charged"
  ["microsoft.servicefabricmesh/applications"]="PaaS_Non_Charged"
  ["microsoft.signalrservice/signalr"]="PaaS_Non_Charged"
  ["microsoft.synapse/workspaces"]="PaaS_Non_Charged"
  ["microsoft.compute/virtualmachines"]="PaaS_Non_Charged"
  ["microsoft.network/virtualnetworkgateways"]="PaaS_Non_Charged"
  ["microsoft.automation/automationaccounts"]="PaaS_Non_Charged"
  ["microsoft.network/virtualhubs"]="PaaS_Non_Charged"
  ["microsoft.network/vpngateways"]="PaaS_Non_Charged"
  ["microsoft.cdn/profiles"]="PaaS_Non_Charged"
  ["microsoft.netapp/netappaccounts"]="PaaS_Non_Charged"
  ["microsoft.network/networkinterfaces"]="PaaS_Non_Charged"
  ["microsoft.insights/components"]="PaaS_Non_Charged"
  ["microsoft.datalakeanalytics/accounts"]="PaaS_Non_Charged"
  ["microsoft.datalakestore/accounts"]="PaaS_Non_Charged"
  ["microsoft.storage/storageaccounts/file"]="PaaS_Non_Charged"
  ["microsoft.storage/storageaccounts/blob"]="PaaS_Non_Charged"
  ["microsoft.storage/storageaccounts/table"]="PaaS_Non_Charged"
  ["microsoft.storage/storageaccounts/queue"]="PaaS_Non_Charged"
  ["microsoft.storage/storageaccounts"]="PaaS_Non_Charged"
  ["microsoft.network/publicipaddresses"]="PaaS_Non_Charged"
  ["microsoft.network/trafficmanagerprofiles"]="PaaS_Non_Charged"
  ["microsoft.streamanalytics/streamingjobs"]="PaaS_Non_Charged"
  ["microsoft.dbformysql/flexibleservers"]="PaaS_Non_Charged"
  ["microsoft.dbforpostgresql/servergroupsv2"]="PaaS_Non_Charged"
  ["microsoft.compute/virtualmachinescalesets"]="PaaS_Non_Charged"
)

declare -A service_count=(
  ["IaaS"]=0
  ["PaaS"]=0
  ["PaaS_Non_Charged"]=0
  ["Non_Supported"]=0
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
    service_count["PaaS_Non_Charged"]=$((service_count["PaaS_Non_Charged"]+$count))
  else
    service_count["Non_Supported"]=$((service_count["Non_Supported"]+$count))
  fi
done < "$azure_resources_csv_file"

for key in "${!service_count[@]}"; do
    value="${service_count[$key]}"
    echo "$key,$value" >> "$output_csv_file"
  done


echo "Output saved to $output_csv_file"

if [ -f "$azure_resources_csv_file" ]; then
    rm -f "$azure_resources_csv_file"
fi