#! /bin/bash

regions=(us-east-1
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

resource_types=(
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

global_resource_types=(
AWS::CloudFront::Distribution
  AWS::S3::Bucket)

iaas=("ec2")
paas=("AWS::ECS::Cluster"
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
# cloud control api resources
total_services=$((${#resource_types[@]} + ${#global_resource_types[@]}))
# aws cli resources
((total_services = total_services + 25))

# write columns to output csv file
echo "Category, Number" >aws_resource_count_output.csv

iaas_count=0
paas_count=0
paas_non_charged_count=0

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
    aws_cli_cmd=$(aws $resource $resource_api --region $region 2>&1)
    # success
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
    # failure
    else
      unsupported_region_aws_error="Could not connect to the endpoint URL"
      if [[ "$aws_cli_cmd" == *"$unsupported_region_aws_error"* ]]; then
        # if a region is not supported for a resource type, we can continue with other regions.
        continue
      else
        echo "AWS Error for $resource_api in $region: $aws_cli_cmd"
      fi
    fi
  done
}

echo "Estimating resource counts for $total_services resource types in ${#regions[@]} regions..."

# app stream fleets
get_resources "appstream" "describe-fleets" ".Fleets"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# auto scaling groups
get_resources "autoscaling" "describe-auto-scaling-groups" ".AutoScalingGroups"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# backup protected resources
get_resources "backup" "list-protected-resources" ".Results"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# cloud search domain
get_resources "cloudsearch" "list-domain-names" ".DomainNames"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# code build projects
get_resources "codebuild" "list-projects" ".projects"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# cognito user pool - max results parameter is required
get_resources "cognito-idp" "list-user-pools --max-results 60" ".UserPools"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# direct connect connections
get_resources "directconnect" "describe-connections" ".connections"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# database migration service - replication instances
get_resources "dms" "describe-replication-instances" ".ReplicationInstances"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# database migration service - replication tasks
get_resources "dms" "describe-replication-tasks" ".ReplicationTasks"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# ec2 instances
get_resources "ec2" "describe-instances" "[.Reservations[].Instances[]]"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# elastictranscoder pipelines
get_resources "elastictranscoder" "list-pipelines" ".Pipelines"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# event bridge rules
get_resources "events" "list-rules" ".Rules"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# fsx file system
get_resources "fsx" "describe-file-systems" ".FileSystems"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# glue jobs
get_resources "glue" "list-jobs" ".JobNames"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# elemental media convert queue
get_resources "mediaconvert" "describe-endpoints" ".Endpoints"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# elemental mediastore container
get_resources "mediastore" "list-containers" ".Containers"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# mq broker
get_resources "mq" "list-brokers" ".BrokerSummaries"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# MSK broker - done in 2 steps -> 1. get clusters 2. get broker nodes for each cluster
for region in ${regions[@]}; do
  aws_cli_cmd=$(aws kafka list-clusters-v2 --region $region 2>&1)

  # success
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

  # failure
  else
    unsupported_region_aws_error="Could not connect to the endpoint URL"
    if [[ "$aws_cli_cmd" == *"$unsupported_region_aws_error"* ]]; then
      # if a region is not supported for a resource type, we can continue with other regions.
      continue
    else
      echo "AWS Error: $aws_cli_cmd"
    fi
  fi
done

((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# neptune db instance
get_resources "neptune" "describe-db-instances" ".DBInstances"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# ops works stack
get_resources "opsworks" "describe-stacks" ".Stacks"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# sagemaker endpoints
get_resources "sagemaker" "list-endpoints" ".Endpoints"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# transfer server
get_resources "transfer" "list-servers" ".Servers"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# workspaces - directory
get_resources "workspaces" "describe-workspace-directories" ".Directories"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# workspaces - workspace
get_resources "workspaces" "describe-workspaces" ".Workspaces"
((processed = processed + 1))
echo -e "\r$(($processed * 100 / $total_services))% done...\c"

# end of aws-cli approach

# list resources for each region and resource type using cloud control api

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
        # if a region doesn't support LIST operation for a resource type, we can skip checking for all other regions.
        break
      fi
    fi
  done
  ((processed = processed + 1))
  echo -e "\r$(($processed * 100 / $total_services))% done...\c"
done

# global resources
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

# EKS count
eks_count=$(kubectl get pods -ojson | jq '.items | length')
if [[ $eks_count -gt 0 ]]; then
  ((paas_count = paas_count + $eks_count))
fi

echo "Done! Results saved in aws_resource_count_output.csv."

echo "IaaS",$iaas_count >>aws_resource_count_output.csv
echo "PaaS",$paas_count >>aws_resource_count_output.csv
echo "PaaS(Non-charged)",$paas_non_charged_count >>aws_resource_count_output.csv