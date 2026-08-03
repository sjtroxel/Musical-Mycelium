# The guardrails. These are not optional extras on this project.
#
# .claude/rules/aws-and-cost.md requires budget alarms and Cost Anomaly Detection to exist BEFORE the
# first `terraform apply`, and the phase-1 definition of done lists "budget alarms armed" as a
# shipping criterion. The $5/$10/$20 ladder was armed by hand before this file existed; these
# resources are what bring it under Terraform so invariant 5 stays true. See infra/README.md for the
# import procedure — running this without importing first will fail on a name collision, or worse,
# quietly create a second set alongside the originals.

resource "aws_budgets_budget" "monthly" {
  for_each = { for amount in var.budget_thresholds : tostring(amount) => amount }

  name         = "${var.project}-monthly-${each.key}"
  budget_type  = "COST"
  limit_amount = tostring(each.value)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Both notifications, not one. ACTUAL tells you money is already spent; FORECASTED tells you the
  # current burn rate will get there — which is the one that arrives early enough to do something
  # about a runaway eval run or a hammered public URL.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}

# Cost Anomaly Detection — the item .claude/rules/aws-and-cost.md has listed as owed since the
# account was created, and the one guardrail budgets cannot provide. A budget answers "have I spent
# too much this month". Anomaly detection answers "is today's spend unlike every other day", which is
# what actually catches a loop that started billing four hours ago on the 3rd of the month.
#
# Free. There is no charge for the service.
resource "aws_ce_anomaly_monitor" "service" {
  name              = "${var.project}-service-monitor"
  monitor_type      = "DIMENSIONAL"
  monitor_dimension = "SERVICE"
}

resource "aws_ce_anomaly_subscription" "alerts" {
  name             = "${var.project}-anomaly-alerts"
  frequency        = "DAILY"
  monitor_arn_list = [aws_ce_anomaly_monitor.service.arn]

  subscriber {
    type    = "EMAIL"
    address = var.alert_email
  }

  # A $1 absolute impact threshold rather than a percentage. On an account whose expected steady state
  # is a few cents, any percentage threshold is either permanently triggered or permanently asleep;
  # a dollar is a real signal here and would be noise on a large account.
  threshold_expression {
    dimension {
      key           = "ANOMALY_TOTAL_IMPACT_ABSOLUTE"
      values        = ["1"]
      match_options = ["GREATER_THAN_OR_EQUAL"]
    }
  }
}
