#! /bin/bash

#############
# VARIABLES #
#############

declare -a regions=(
  us-east-1
  us-east-2
  us-west-1
  us-west-2
  eu-central-1
  eu-north-1
  eu-south-1
  eu-west-1
  eu-west-2
  eu-west-3
  ap-east-1
  ap-northeast-1
  ap-northeast-2
  ap-northeast-3
  ap-south-1
  ap-southeast-1
  ap-southeast-2
  ap-southeast-3
  af-south-1
  ca-central-1
  me-south-1
  sa-east-1)

declare -a resource_types=(
AWS::ApiGateway::RestApi
  AWS::ApiGatewayV2::Api
  AWS::Athena::WorkGroup
  AWS::Backup::BackupVault
  AWS::DocDBElastic::Cluster
  AWS::DynamoDB::Table
  AWS::EC2::NatGateway
  AWS::EC2::TransitGatewayAttachment
  AWS::EC2::TransitGateway
  AWS::EC2::VPNConnection
  AWS::EC2::Volume
  AWS::ECS::Cluster
  AWS::EFS::FileSystem
  AWS::ElasticBeanstalk::Environment
  AWS::EMRContainers::VirtualCluster
  AWS::KinesisFirehose::DeliveryStream
  AWS::KinesisVideo::Stream
  AWS::Kinesis::Stream
  AWS::Lambda::Function
  AWS::Lightsail::LoadBalancer
  AWS::MediaConnect::Flow
  AWS::MediaPackage::Channel
  AWS::MediaPackage::PackagingGroup
  AWS::MSK::Cluster
  AWS::RDS::DBInstance
  AWS::Redshift::Cluster
  AWS::Route53::HealthCheck
  AWS::SES::ConfigurationSet
  AWS::SNS::Topic
  AWS::SQS::Queue
  AWS::StepFunctions::StateMachine)

declare -a global_resource_types=(
AWS::CloudFront::Distribution
  AWS::S3::Bucket)

declare -a iaas=(
  "ec2")

declare -a paas=(
  "AWS::ECS::Cluster"
  "AWS::Lambda::Function"
  "appstream"
  "cloudsearch"
  "AWS::DocDBElastic::Cluster"
  "glue"
  "kafka"
  "mq"
  "AWS::Redshift::Cluster"
  "AWS::RDS::DBInstance")

processed=0
# Cloud control api resources
total_services=$((${#resource_types[@]} + ${#global_resource_types[@]}))

iaas_count=0
paas_count=0
paas_non_charged_count=0

output_csv_file="aws_resource_count_output.csv"

#############
# FUNCTIONS #
#############

function show_help() {
    echo "Usage: $0 [-h] [-o output_file_name] [-r regions]"
    echo " -h help       Display this help message."
    echo " -r regions    Comma separated list of regions to include in the resource count(in double quotes). If not provided, all regions will be included."
    echo " -o output     Output file name. If not provided, the default name will be used - azure_resource_count_output.csv."
    exit 0
}

function update_count() {
  res_type=$1
  resource_count=$2
  case $res_type in
    IaaS)
      ((iaas_count = iaas_count + $resource_count));;
    PaaS)
      ((paas_count = paas_count + $resource_count));;
    *)
      ((paas_non_charged_count = paas_non_charged_count + $resource_count));;
  esac
}

function get_resources() {
  # Set connection timeout to 10 seconds
  cli_connect_timeout=10

  resource=$1
  resource_api=$2
  resource_identifier=$3
  res_type="PaaS(Non-charged)"

  if [[ $(echo ${iaas[@]} | fgrep -w $resource) ]]
  then
    res_type="IaaS"
  elif [[ $(echo ${paas[@]} | fgrep -w $resource) ]]
   then
     res_type="PaaS"
  fi

  if [ -z "$4" ]
    then
      get_regions=("${regions[@]}")
    else
      get_regions=("$4")
  fi

  for region in "${get_regions[@]}"; do
    aws_cli_cmd=$(aws $resource $resource_api --region $region 2>&1 --cli-connect-timeout $cli_connect_timeout)
    # Success
    if [[ $? -eq 0 ]]; then
      next_token=$(echo "$aws_cli_cmd" | jq -r ".NextToken")
      length=$(echo "$aws_cli_cmd" | jq "$resource_identifier | length")
      update_count $res_type $length

      while [ "$next_token" != "null" ]; do
        paginate_aws_cli_cmd=$(aws $resource $resource_api --region $region --starting-token $next_token)
        next_token=$(echo "$paginate_aws_cli_cmd" | jq -r ".NextToken")
        count=$(echo "$paginate_aws_cli_cmd" | jq "$resource_identifier | length")
        update_count $res_type $count
      done
    # Failure
    else
      if [[ "$aws_cli_cmd" == *"Could not connect to the endpoint URL"* ]] || [[ "$aws_cli_cmd" == *"Connect timeout on endpoint URL"* ]] ; then
        # If a region is not supported for a resource type, we can continue with other regions.
        continue
      else
        echo "AWS Error for $resource_api in $region: $aws_cli_cmd"
      fi
    fi
  done
}

#############
#    MAIN   #
#############

# Get options from the command line
while getopts o:r:h flag
do
    case "${flag}" in
        r) IFS=',' read -r -a regions <<< "${OPTARG}";;
        o) output_csv_file="${OPTARG}";;
        h) show_help;;
    esac
done
shift $((OPTIND-1))

# AWS cli resources
((total_services = total_services + 25))

# Remove previous resource count file if it exists
if [ -f "$output_csv_file" ]; then
  echo "Removing previous output file: $output_csv_file"
  rm -f "$output_csv_file"
fi

echo "Estimating resource counts for $total_services resource types in ${#regions[@]} regions..."

# App stream fleets
get_resources "appstream" "describe-fleets" ".Fleets"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# Auto scaling groups
get_resources "autoscaling" "describe-auto-scaling-groups" ".AutoScalingGroups"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# Backup protected resources
get_resources "backup" "list-protected-resources" ".Results"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# Cloud search domain
get_resources "cloudsearch" "list-domain-names" ".DomainNames"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# Code build projects
get_resources "codebuild" "list-projects" ".projects"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# Cognito user pool - max results parameter is required
get_resources "cognito-idp" "list-user-pools --max-results 60" ".UserPools"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# Direct connect connections
get_resources "directconnect" "describe-connections" ".connections"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# Database migration service - replication instances
get_resources "dms" "describe-replication-instances" ".ReplicationInstances"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# Database migration service - replication tasks
get_resources "dms" "describe-replication-tasks" ".ReplicationTasks"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# EC2 instances
get_resources "ec2" "describe-instances" "[.Reservations[].Instances[]]"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# Elastictranscoder pipelines
get_resources "elastictranscoder" "list-pipelines" ".Pipelines"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# Event bridge rules
get_resources "events" "list-rules" ".Rules"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# FSX file system
get_resources "fsx" "describe-file-systems" ".FileSystems"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# Glue jobs
get_resources "glue" "list-jobs" ".JobNames"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# Elemental media convert queue
get_resources "mediaconvert" "describe-endpoints" ".Endpoints"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# Elemental mediastore container
get_resources "mediastore" "list-containers" ".Containers"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# MQ broker
get_resources "mq" "list-brokers" ".BrokerSummaries"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# MSK broker - done in 2 steps -> 1. get clusters 2. get broker nodes for each cluster
for region in ${regions[@]}; do
  aws_cli_cmd=$(aws kafka list-clusters-v2 --region $region 2>&1)

  # Success
  if [[ $? -eq 0 ]]; then
    next_token=$(echo "$aws_cli_cmd" | jq -r ".NextToken")
    cluster_arns=$(echo "$aws_cli_cmd" | jq -r ".ClusterInfoList | .[].ClusterArn")

    for arn in $cluster_arns; do
      get_resources "kafka" "list-nodes --cluster-arn $arn" ".NodeInfoList" $1 $region
    done

    while [ "$next_token" != "null" ]; do
      paginate_aws_cli_cmd=$(aws kafka list-clusters-v2 --region $region --starting-token $next_token)
      next_token=$(echo "$paginate_aws_cli_cmd" | jq -r ".NextToken")
      cluster_arns=$(echo "$paginate_aws_cli_cmd" | jq -r ".ClusterInfoList | .[].ClusterArn")

      for arn in $cluster_arns; do
        get_resources "kafka" "list-nodes --cluster-arn $arn" ".NodeInfoList" $1 $region
      done
    done

  # Failure
  else
    unsupported_region_aws_error="Could not connect to the endpoint URL"
    if [[ "$aws_cli_cmd" == *"$unsupported_region_aws_error"* ]]; then
      # If a region is not supported for a resource type, we can continue with other regions.
      continue
    else
      echo "AWS Error: $aws_cli_cmd"
    fi
  fi
done

((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# Neptune db instance
get_resources "neptune" "describe-db-instances" ".DBInstances"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# Ops works stack
get_resources "opsworks" "describe-stacks" ".Stacks"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# Sagemaker endpoints
get_resources "sagemaker" "list-endpoints" ".Endpoints"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# Transfer server
get_resources "transfer" "list-servers" ".Servers"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# Workspaces - directory
get_resources "workspaces" "describe-workspace-directories" ".Directories"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# Workspaces - workspace
get_resources "workspaces" "describe-workspaces" ".Workspaces"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# End of aws-cli approach

# List resources for each region and resource type using cloud control api

for type in ${resource_types[@]}; do
  res_type="PaaS(Non-charged)"

  if [[ $(echo ${iaas[@]} | fgrep -w $type) ]]
    then
      res_type="IaaS"
    elif [[ $(echo ${paas[@]} | fgrep -w $type) ]]
     then
       res_type="PaaS"
  fi

  for region in ${regions[@]}; do
    result=$(aws cloudcontrol list-resources --type-name $type --region $region 2>&1)
    if [[ $? -eq 0 ]]; then
      resources=$(echo "$result" | jq '.ResourceDescriptions | length')
      update_count $res_type $resources
    else
      unsupported_error='does not support LIST action'
      if [[ "$result" == *"$unsupported_error"* ]]; then
        # If a region doesn't support LIST operation for a resource type, we can skip checking for all other regions.
        break
      fi
    fi
  done
  ((processed = processed + 1))
  echo -e "\r$(($processed * 100 / $total_services))% done...\c"
done

# Global resources
for type in ${global_resource_types[@]}; do
  res_type="PaaS(Non-charged)"

  if [[ $(echo ${iaas[@]} | fgrep -w $type) ]]
    then
      res_type="IaaS"
    elif [[ $(echo ${paas[@]} | fgrep -w $type) ]]
     then
       res_type="PaaS"
  fi
  result=$(aws cloudcontrol list-resources --type-name $type --region $regions 2>&1)
  if [[ $? -eq 0 ]]; then
    resources=$(echo "$result" | jq '.ResourceDescriptions | length')
    update_count $res_type $resources
  fi
  ((processed = processed + 1))
  echo -e "\r$(($processed * 100 / $total_services))% done...\c"
done

echo "Category,Number" >> "$output_csv_file"
echo "IaaS",$iaas_count >> "$output_csv_file"
echo "PaaS",$paas_count >> "$output_csv_file"
echo "Non-compute",$paas_non_charged_count >> "$output_csv_file"

echo -e "\nDone! Results saved in $output_csv_file."
