"""Safe-to-understand CLI for the ADM-005 trusted worker proof."""
import argparse
import json
import time
from .worker import WorkerSupervisor


def main():
    parser=argparse.ArgumentParser(description='ADM-005 trusted worker supervisor')
    parser.add_argument('--state',default='.adm-worker-state')
    actions=parser.add_subparsers(dest='action',required=True)
    a=actions.add_parser('add')
    a.add_argument('--label',required=True)
    a.add_argument('--cwd',required=True)
    a.add_argument('cmd',nargs=argparse.REMAINDER)
    r=actions.add_parser('run')
    r.add_argument('--timeout',type=float,default=30)
    r.add_argument('--continuous',action='store_true')
    actions.add_parser('recover')
    actions.add_parser('status')
    args=parser.parse_args()
    manager=WorkerSupervisor(args.state)
    try:
        if args.action=='add':
            cmd=args.cmd[1:] if args.cmd[:1]==['--'] else args.cmd
            print(json.dumps({'job_id':manager.add(args.label,cmd,args.cwd)}))
        elif args.action=='recover':
            print(json.dumps(manager.recover()))
        elif args.action=='status':
            print(json.dumps(manager.status(),indent=2))
        else:
            manager.recover()
            while True:
                result=manager.run_once(timeout=args.timeout)
                if result: print(json.dumps(result,indent=2))
                if not args.continuous or result is None: break
    finally:
        manager.close()

if __name__=='__main__':
    main()
