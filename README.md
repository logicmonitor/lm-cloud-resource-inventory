# LM Cloud Resource Inventory

## *What is the purpose of the LM Cloud Resource Inventory scripts?*

This solution is provided by LogicMonitor in order to collect cloud resource counts within an AWS or Azure environment, for LogicMonitor licensing.

## *What data is collected by the LM Cloud Resource Inventory scripts?*

The LM Cloud Resource Inventory script records the associated quantity of services/resources based on LM Cloud resource type (IaaS, PaaS, Non-Compute.)
* By default, no other data associated with cloud resources is collected or recorded (for example, resource name or ID, unless instructed using the *-DetailedResults* parameter.) 
* The output of the script is visible to customers for review, prior to sharing with LogicMonitor.

## *How will LogicMonitor use this data?*

The data collected will be used to accurately scope the quantity of LogicMonitor cloud resource licenses required for quoting. For example, the scripts will return the total number of IaaS or PaaS resources in an AWS account or Azure subscription.

## *What language are these scripts written in?*

The scripts provided are PowerShell scripts that LogicMonitor recommends executing at the cloud provider CLI.

## *Where should I execute these scripts in order to successfully collect data?*

In order to minimize setup requirements, and for purposes of expediency, LogicMonitor recommends execution of the scripts in the relevant cloud provider CLI.

For users with advanced cloud experience, the scripts can also be executed from a local workstation with the AWS or Azure pre-reqs installed.

## Requirements

**Note:**  Cloud provider CLIs have all required dependencies already installed.

**AWS**
* PowerShell AWS.Tools module - [How to install the AWS.Tools PowerShell module](https://docs.aws.amazon.com/powershell/latest/userguide/pstools-getting-set-up.html)
* PowerShell version 5.1 or later
  
**Azure**
* PowerShell Az module - [How to install the PowerShell Az module](https://learn.microsoft.com/en-us/powershell/azure/install-azps-windows?view=azps-12.3.0&tabs=powershell&pivots=windows-psgallery)
* PowerShell version 5.1 or later

## *What permissions are required by the scripts to run against my cloud environments?*

The scripts will utilize the permissions of the currently logged-in cloud account, and while the scripts do not execute any write operations against a cloud account, best practice recommendation is to run the scripts with a read-only account.

**AWS**
* Minimum required role: ReadOnly (best practice is to use an account with only ReadOnly access.)
* For AWS Organizations:
  - The role specified in the -AssumeRole parameter must exist in all member accounts and have ReadOnly permissions.
  - The account running the script must have permission to assume this role in the member accounts.
  - Recommended to use a dedicated role like "OrganizationAccountAccessRole" with ReadOnly permissions for inventory purposes.

**Azure**
* Minimum required role: Reader (best practice is to use an account with only Reader access.)

## *Does the script make any connections, other than to AWS or Azure?*

No, the script(s) don’t establish any external connections, they simply query Azure and AWS, and write output to a .csv file.

## *How long should it take to run these scripts?*

**AWS**
* The AWS script execution time can vary significantly:
  - It may take up to an hour to complete, as it checks each service in every region for accessible resources.
  - By default, the script includes all AWS regions in its scan.
  - To reduce the overall runtime, it's recommended to use the *-Regions* parameter. This allows you to limit the scope to only the regions you actively use.
* For AWS Organizations users:
  - The script can inventory resources across multiple accounts within an Organizational Unit (OU).
  - Use the *-OrganizationalUnitId* parameter to specify the OU you want to inventory.
  - The *-AssumeRole* parameter allows the script to access member accounts securely.
  - This feature enables a comprehensive inventory across your entire AWS organization structure.

**Azure**
* Depending on how many subscriptions are being counted the script typically takes around 2-3 minutes per subscription. By default all subscriptions and resource groups are included. Subscriptions can be specified using the *-Subscriptions* parameter as a comma separated list of subscriptions. Resource Groups can be specified using the *-ResourceGroups* parameter as a comma separated list of resource groups.

## How to run the provided scripts?

See below for examples on running the LM Cloud Resource Inventory scripts. For a list of all parameters you can use the *-h* flag to show all options:

**AWS**
```
#Make the script executable
pwsh

#Run resource count script for two regions (us-east-1, us-east-2)
.\get_aws_resource_counts.ps1 -Regions "us-east-1,us-east-2"

#Run resource count script for all regions with a output file named aws_resource_count_output.csv
.\get_aws_resource_counts.ps1 -OutputFile aws_resource_count_output.csv

#Run resource count script for all regions and include a detailed inventory file with the results
$results = .\get_aws_resource_counts.ps1 -DetailedResults -PassThru

#Run resource count script for an Organizational Unit (OU) with ID "ou-1234-5678abcd" and assume role "OrganizationAccountAccessRole" in member accounts
.\get_aws_ou_resource_counts.ps1 -OrganizationalUnitId "ou-1234-5678abcd" -AssumeRole "OrganizationAccountAccessRole" -OutputFile "ou_resource_counts.csv"

#Run resource count script for an OU with ID "ou-9876-dcba4321", assume role "CustomInventoryRole", include detailed results, and limit to specific regions
.\get_aws_ou_resource_counts.ps1 -OrganizationalUnitId "ou-9876-dcba4321" -AssumeRole "CustomInventoryRole" -DetailedResults -Regions "us-east-1,us-west-2"

#Run resource count script for an OU with ID "ou-abcd-1234efgh", assume role "ResourceInventoryRole", pass through results, and use a custom global region
$results = .\get_aws_ou_resource_counts.ps1 -OrganizationalUnitId "ou-abcd-1234efgh" -AssumeRole "ResourceInventoryRole" -PassThru -GlobalRegion "us-west-2"


```

**Azure**
```
#Start a PowerShell session
pwsh

#Run resource count script for two subscriptions (Pay-As-You-Go & Production)
.\get_azure_resource_counts.ps1 -Subscriptions "Pay-As-You-Go,Production" -OutputFile "custom_output.csv"

#Run resource count script for all subscriptions with a output file named azure_resource_count_output.csv
.\get_azure_resource_counts.ps1 -OutputFile azure_resource_count_output.csv

#Run resource count script for all subscriptions and include a detailed inventory file with the results
$results = .\get_azure_resource_counts.ps1 -DetailedResults -PassThru
```

## *What outputs do the scripts provide?*

The script outputs are provided as CSV files that can be reviewed by customers, prior to sharing with LogicMonitor. Unless specified when running the resource count scripts, the default output files names are:
```
aws_resource_count_output(_detailed).csv
azure_resource_count_output(_detailed).csv
```

Example CSV output:
```
Category,Number
IaaS,71
PaaS,15
Non-Compute,349
```

Example details Azure CSV output:
```
"Subscription","ResourceGroup","ResourceName","Location","Category"
"MySub","RG1","cs21003200186d3f527","eastus","Non-compute"
"MySub","RG2","lmdb1/master","westus","PaaS"
rest of inventory....
```

Example details AWS CSV output:
```
"ResourceType","Type","Count"
"AWS::Athena::WorkGroup","Non-Compute","1"
"AWS::Backup::BackupVault","Non-Compute","1"
"AWS::Bedrock::FoundationModels","PaaS","68"
"AWS::DynamoDB::Table","Non-Compute","1"
rest of inventory....
```

## *What should we do with the outputs after we're done running these scripts?*

LogicMonitor recommends reviewing the output(s) of the script(s) prior to sharing with LogicMonitor, so as to ensure comfort with the information being provided.

The outputs can be downloaded from the provider's cloud shell:
* [Download files from AWS CloudShell](https://docs.aws.amazon.com/cloudshell/latest/userguide/getting-started.html#download-file)
* [Download files from the Azure Cloud Shell](https://learn.microsoft.com/en-us/azure/cloud-shell/persisting-shell-storage#download-files-in-azure-cloud-shell)

## *How to calculate Kubernetes resource counts?*

LogicMonitor recommends utilizing kubectl in order to get resource counts for all K8s deployments whether that be EKS,AKS or self hosted. For each cluster you manage you can run the following command to get the number of pods in the required clusters:

```
kubectl get pods --all-namespaces --no-headers -o custom-columns=Type:kind | sort | uniq -c
```

## *Where can we get support if we have questions or concerns about running these scripts?*

As these scripts are most commonly utilized in the LogicMonitor pre-sales process, reach out to your friendly neighborhood Sales Engineer or Customer Success Manager for additional support.
