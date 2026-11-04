import argparse, json, time
from .core import Supervisor,resources,mode
p=argparse.ArgumentParser(description='ADM architecture proof — local command supervisor')
p.add_argument('--root',default='.adm-state')
s=p.add_subparsers(dest='action',required=True)
s.add_parser('probe');s.add_parser('status');r=s.add_parser('run');r.add_argument('--timeout',type=int,default=120);r.add_argument('--continuous',action='store_true')
a=s.add_parser('add');a.add_argument('--name',required=True);a.add_argument('--cwd',required=True);a.add_argument('--retries',type=int,default=2);a.add_argument('command',nargs=argparse.REMAINDER)
args=p.parse_args()
if args.action=='probe':
    info=resources();print(json.dumps({'resources':info,'mode':mode(info)},indent=2));raise SystemExit
sp=Supervisor(args.root)
try:
    if args.action=='add':
        cmd=args.command[1:] if args.command[:1]==['--'] else args.command
        print('Task',sp.add(args.name,cmd,args.cwd,args.retries))
    elif args.action=='status':print(json.dumps(sp.status(),indent=2))
    elif args.action=='run':
        while True:
            result=sp.run_next(args.timeout)
            if result:print(json.dumps(result,indent=2))
            if not args.continuous or not result:break
finally:sp.close()
