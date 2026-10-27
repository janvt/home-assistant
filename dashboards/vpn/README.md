# VPN dashboard

The **VPN** dashboard (`/dashboard-vpn/usage`) shows the WireGuard VPN on AWS
for the month: how much of AWS's free 100 GB of egress it has used, per peer,
the pace for the rest of the month, the AWS bill and the instance state, and
30 days of history.

It isn't in the sidebar. The VPN alert pills on the Mobile dashboard open it:
tap a VPN card on the Alerts page, or **Details** in the VPN section there.

| File | What |
|------|------|
| [`build.py`](build.py) | Builds the whole dashboard config. Pure functions. `LINK` is the path the pills use. |
| [`sync.py`](sync.py) | Creates the dashboard if needed (not in the sidebar) and pushes it. |

```bash
python sync.py            # dry run
python sync.py --apply    # create and save
```

Everything on it comes from the `input_number.wg_vpn_*` helpers, written by
the wg-vpn Terraform stack's EventBridge webhook (automation "WG VPN: receive
AWS EventBridge").
