
import tkinter as tk
from tkinter import ttk, messagebox

CALLSIGNS = {
    "DAH":"AIR ALGERIE","DTR":"TASSILI","THY":"TURKISH","QTR":"QATARI",
    "TAR":"TUNAIR","AFR":"AIR FRANCE","DLH":"LUFTHANSA",
    "UAE":"EMIRATES","ETD":"ETIHAD"
}

SEPARATION=3
CAPACITY=60//SEPARATION
flights=[]

def add():
    f=flight.get().upper().strip()
    op=operation.get()
    t=timev.get().strip()
    ac=aircraft.get().strip()
    if len(f)<3 or ":" not in t:
        messagebox.showerror("Error","Check flight/time")
        return
    cs=CALLSIGNS.get(f[:3],"UNKNOWN")
    flights.append({"flight":f,"callsign":cs,"operation":op,"time":t,"aircraft":ac})
    refresh()

def refresh():
    for i in tree.get_children():
        tree.delete(i)
    arr=dep=0
    for fl in flights:
        tree.insert("", "end", values=(fl["flight"],fl["callsign"],fl["aircraft"],fl["operation"],fl["time"]))
        if fl["operation"]=="Arrival":
            arr+=1
        else:
            dep+=1
    if config.get()=="SINGLE":
        demand=arr+dep
        cong=max(0,demand-CAPACITY)
        status=f"Single | Demand={demand} Capacity={CAPACITY} Congestion={cong}"
    else:
        acg=max(0,arr-CAPACITY)
        dcg=max(0,dep-CAPACITY)
        status=f"Dual | Arr:{arr}/{CAPACITY} Cong:{acg}  Dep:{dep}/{CAPACITY} Cong:{dcg}"
    lbl.config(text=status)

root=tk.Tk()
root.title("Airport Congestion Management System")
config=tk.StringVar(value="DUAL")

frm=tk.Frame(root); frm.pack(padx=10,pady=10)

tk.Label(frm,text="Flight").grid(row=0,column=0)
flight=tk.Entry(frm,width=10); flight.grid(row=0,column=1)
tk.Label(frm,text="Aircraft").grid(row=0,column=2)
aircraft=tk.Entry(frm,width=8); aircraft.grid(row=0,column=3)
tk.Label(frm,text="Operation").grid(row=1,column=0)
operation=ttk.Combobox(frm,values=["Arrival","Departure"],width=12)
operation.current(0); operation.grid(row=1,column=1)
tk.Label(frm,text="ETA/ETD").grid(row=1,column=2)
timev=tk.Entry(frm,width=8); timev.grid(row=1,column=3)

ttk.Combobox(frm,textvariable=config,values=["SINGLE","DUAL"],width=10).grid(row=0,column=4,padx=5)
tk.Button(frm,text="Add Flight",command=add).grid(row=1,column=4)

tree=ttk.Treeview(root,columns=("F","C","A","O","T"),show="headings")
for c,h,w in [("F","Flight",90),("C","Call Sign",140),("A","Aircraft",80),("O","Operation",90),("T","Time",70)]:
    tree.heading(c,text=h); tree.column(c,width=w)
tree.pack(fill="both",expand=True,padx=10,pady=10)

lbl=tk.Label(root,text="")
lbl.pack(pady=5)
refresh()
root.mainloop()
