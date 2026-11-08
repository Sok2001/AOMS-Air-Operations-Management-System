"""
Airport Management System (Mini ATFM)
Features:
- Flight database
- Arrival/Departure management
- Congestion calculation
- Single/Dual runway mode
- Search-ready structure
This is a starter project that can be extended.
"""
import tkinter as tk
from tkinter import ttk, messagebox

CALLSIGNS={"DAH":"AIR ALGERIE","DTR":"TASSILI","THY":"TURKISH","QTR":"QATARI","TAR":"TUNAIR","AFR":"AIR FRANCE","DLH":"LUFTHANSA","UAE":"EMIRATES","ETD":"ETIHAD"}
CAPACITY=20
SEP=3
flights=[]

def calc():
    arr=sum(f["op"]=="Arrival" for f in flights)
    dep=sum(f["op"]=="Departure" for f in flights)
    if mode.get()=="SINGLE":
        dem=arr+dep
        cong=max(0,dem-CAPACITY)
        txt=f"Demand={dem} Capacity={CAPACITY} Congestion={cong}"
    else:
        txt=f"ARR {arr}/{CAPACITY} Cong={max(0,arr-CAPACITY)} | DEP {dep}/{CAPACITY} Cong={max(0,dep-CAPACITY)}"
    status.config(text=txt)

def add():
    f=flight.get().upper()
    if len(f)<3:return
    row=(f,CALLSIGNS.get(f[:3],"UNKNOWN"),atype.get(),wake.get(),op.get(),origin.get(),dest.get(),rwy.get(),time.get(),stat.get())
    flights.append({"op":op.get()})
    tree.insert("",tk.END,values=row)
    calc()

root=tk.Tk()
root.title("Airport Management System")
mode=tk.StringVar(value="DUAL")
top=tk.Frame(root); top.pack(padx=8,pady=8)
for i,(lab,var,w) in enumerate([
("Flight",tk.Entry(top,width=10),None),
("Aircraft",tk.Entry(top,width=8),None),
("Wake",ttk.Combobox(top,values=["L","M","H"],width=3),None),
("Operation",ttk.Combobox(top,values=["Arrival","Departure"],width=10),None),
("Origin",tk.Entry(top,width=6),None),
("Destination",tk.Entry(top,width=6),None),
("Runway",tk.Entry(top,width=4),None),
("ETA/ETD",tk.Entry(top,width=6),None),
("Status",ttk.Combobox(top,values=["Scheduled","Boarding","Airborne","Landed"],width=10),None)
]): pass
flight=tk.Entry(top,width=10);atype=tk.Entry(top,width=8);wake=ttk.Combobox(top,values=["L","M","H"],width=3);wake.set("M");op=ttk.Combobox(top,values=["Arrival","Departure"],width=10);op.set("Arrival");origin=tk.Entry(top,width=6);dest=tk.Entry(top,width=6);rwy=tk.Entry(top,width=4);time=tk.Entry(top,width=6);stat=ttk.Combobox(top,values=["Scheduled","Boarding","Airborne","Landed"],width=10);stat.set("Scheduled")
widgets=[("Flight",flight),("Aircraft",atype),("Wake",wake),("Operation",op),("Origin",origin),("Destination",dest),("Runway",rwy),("ETA/ETD",time),("Status",stat)]
for c,(l,wid) in enumerate(widgets):
    tk.Label(top,text=l).grid(row=0,column=c)
    wid.grid(row=1,column=c)
ttk.Combobox(top,textvariable=mode,values=["SINGLE","DUAL"],width=8).grid(row=1,column=len(widgets))
tk.Button(top,text="Add Flight",command=add).grid(row=1,column=len(widgets)+1)

cols=("Flight","Callsign","Aircraft","Wake","Operation","Origin","Destination","Runway","Time","Status")
tree=ttk.Treeview(root,columns=cols,show="headings",height=12)
for c in cols:
    tree.heading(c,text=c); tree.column(c,width=90)
tree.pack(fill="both",expand=True,padx=8,pady=8)
status=tk.Label(root,text="Ready")
status.pack()
root.mainloop()
