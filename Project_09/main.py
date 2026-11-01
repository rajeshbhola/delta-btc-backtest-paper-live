"""CLI for the offline BTC strategy performance analyzer."""
import argparse
import sys
from pathlib import Path
from performance_lab.files import process_one, load_report, available_timeframes
from performance_lab.metrics import TIMEFRAME_SECONDS


def main(argv=None):
    parser = argparse.ArgumentParser(description='BTC Strategy Performance Analyzer — Project 9 (JSON only)')
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('analyze', help='Analyze Project 8 equity and closed trades')
    run.add_argument('--input', default='demo_project8', help='Project 8 results root, e.g. demo_results')
    run.add_argument('--output', default='reports')
    run.add_argument('--timeframes', nargs='+', choices=list(TIMEFRAME_SECONDS), default=['5m'])
    run.add_argument('--risk-free-annual', type=float, default=0.0,
                     help='Annual risk-free rate as decimal; e.g. 0.05 for 5%%. Default 0.')
    summary = sub.add_parser('summary', help='Print already-computed metrics')
    summary.add_argument('--output', default='demo_reports')
    summary.add_argument('--timeframe', default='5m', choices=list(TIMEFRAME_SECONDS))
    compare = sub.add_parser('compare', help='Compare analyzed timeframes')
    compare.add_argument('--output', default='demo_reports')
    args = parser.parse_args(argv)
    try:
        if args.command == 'analyze':
            for tf in args.timeframes:
                data = process_one(args.input, args.output, tf, args.risk_free_annual)
                eq, trades = data['equity_metrics'], data['trade_metrics']
                print(f'{tf:>3}: return={eq["total_return_pct"]:+.3f}% | max DD={eq["max_drawdown_pct"]:.3f}% | closed trades={trades["closed_trades"]} | warnings={len(data["warnings"])}')
            print(f'JSON analysis saved in {Path(args.output).resolve()}')
        elif args.command == 'summary':
            data = load_report(args.output,args.timeframe)
            print(f'BTCUSD {args.timeframe} historical performance (not live)')
            for title, metricset in (('EQUITY', data['equity_metrics']), ('TRADES', data['trade_metrics'])):
                print(f'\n{title}')
                for k,v in metricset.items():
                    print(f'  {k}: {v if v is not None else "N/A"}')
            print('\nWarnings:')
            for warning in data['warnings']:
                print(' -', warning)
        elif args.command == 'compare':
            found = available_timeframes(args.output)
            if not found:
                print('No analyzed timeframes found in', args.output)
                return 1
            print(f'{"TF":<6} {"Return%":>12} {"Max DD%":>12} {"Sharpe":>12} {"Sortino":>12} {"PF":>12} {"Trades":>8}')
            for tf in found:
                data = load_report(args.output,tf)
                a,b=data['equity_metrics'], data['trade_metrics']
                fmt=lambda n: f'{n:.3f}' if isinstance(n,(float,int)) else 'N/A'
                print(f'{tf:<6} {fmt(a["total_return_pct"]):>12} {fmt(a["max_drawdown_pct"]):>12} {fmt(a["sharpe_ratio"]):>12} {fmt(a["sortino_ratio"]):>12} {fmt(b["profit_factor"]):>12} {b["closed_trades"]:>8}')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
