# LM Cloud Resource Inventory

#### *What is the purpose of the LM Cloud Resource Inventory scripts?*

This solution is provided by LogicMonitor in order to collect cloud resource counts within an AWS or Azure environment, for LogicMonitor licensing.

#### *What data is collected by the LM Cloud Resource Inventory scripts?*

LM Cloud Resource Inventory collects the names of cloud resource groups, the types of cloud services being utilized, and the associated quantity of said services/ resources.
* The scripts collect only the “Resource Group” name of each cloud service type.
* No other data associated with cloud resources is collected or recorded (for example, resource name or ID.) 
* The output of the script is visible to customers for review, prior to sharing with LogicMonitor.

#### *How will LogicMonitor use this data?*

The data collected will be used to accurately scope the quantity of LogicMonitor cloud resource licenses required for quoting. For example, the scripts will return the total number of IaaS or PaaS resources in an AWS account or Azure subscription.

#### *What language are these scripts written in?*

The scripts provided are shell scripts that LogicMonitor recommends executing at the cloud provider CLI.

#### *Where should I execute these scripts in order to successfully collect data?*

In order to minimize setup requirements, and for purposes of expediency, LogicMonitor recommends execution of the scripts in the relevant cloud provider CLI.

For users with advanced cloud experience, the scripts can also be executed from a local workstation with the AWS or Azure CLIs installed.

AWS
* [Install or Update the latest version of AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
* Required extensions: TBD
  
Azure
* [How to install the Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
* Required extensions: resource-graph, virtual-wan

#### *What permissions are required by the scripts to run against my cloud environments?*

The scripts will utilize the permissions of the currently logged-in cloud account, and while the scripts do not execute any write operations against a cloud account, best practice recommendation is to run the scripts with a read-only account.

AWS
* Minimum required role: ReadOnly (best practice is to use an account with only ReadOnly access.)

Azure
* Minimum required role: Reader (best practice is to use an account with only Reader access.)

#### *Does the script make any connections, other than to AWS or Azure?*

No, the script(s) don’t establish any external connections, they simply query Azure and AWS, and write output to a .csv file.

#### *How long should it take to run these scripts?*

AWS
* The AWS script may take up to an hour as it needs to check per service, per region, for accessible resources.

Azure
* The Azure script may take up to ten minutes to successfully collect data.

#### *What outputs do the scripts provide?*

The script outputs are provided as CSV files that can be reviewed by customers, prior to sharing with LogicMonitor.
* aws_resource_count_output.csv
* azure_resource_count_output.csv

Example CSV output:
* IaaS,71
* PaaS,15
* Non-Compute,349

#### *What should we do with the outputs after we're done running these scripts?*

LogicMonitor recommends reviewing the output(s) of the script(s) prior to sharing with LogicMonitor, so as to ensure comfort with the information being provided.

The outputs can be downloaded from the provider's cloud shell:
* [Download a file from AWS CloudShell](https://docs.aws.amazon.com/cloudshell/latest/userguide/getting-started.html#download-file)
* [Download Files from the Azure Cloud Shell](https://learn.microsoft.com/en-us/azure/cloud-shell/persisting-shell-storage#download-files-in-azure-cloud-shell)

If additional assistance is required, please reach out to your friendly neighborhood Account Executive or Sales Engineer.

#### *Where can we get support if we have questions or concerns about running these scripts?*

As these scripts are most commonly utilized in the LogicMonitor pre-sales process, reach out to your friendly neighborhood Sales Engineer or Customer Success Manager for additional support.
