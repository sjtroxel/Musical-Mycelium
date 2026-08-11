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

  # MEASURE GROSS SPEND, NOT WHAT IS LEFT TO PAY AFTER CREDITS. Added 2026-08-11.
  #
  # AWS Budgets includes credits by default, which means a budget tracks cost *after* promotional
  # credits are applied. This account is carrying ~$160 of them, so with the default the entire
  # $5/$10/$20 ladder reads near-zero and never fires for as long as the credits last — and then
  # starts firing at full burn rate the moment they run out, with no ramp and no warning.
  #
  # That is the exact failure mode behind the widely-reported 2026 case where Activate credits
  # silently absorbed ~$8k before the invoice appeared. The alarm was working as configured; it was
  # configured to watch the wrong number.
  #
  # These alarms exist to catch a runaway eval run (the docs put the suite at $5-25/run, the largest
  # line item in the project) or a hammered public URL on `llm_provider=bedrock`. Both are situations
  # where credits would be doing the absorbing, so the default setting blinds the guardrail precisely
  # when it is needed. Expect alarm emails during the credit period. That is the point: it means the
  # ladder is tracking real burn rather than reporting a subsidised zero.
  cost_types {
    include_credit = false
  }

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
