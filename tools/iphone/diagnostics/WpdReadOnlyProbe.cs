// Exploratory metadata-only WPD probe. Not a production exporter; see handoff.
using System;
using System.Linq;
using System.Collections.Generic;
using System.Runtime.InteropServices;
namespace MirrorAudit {
[StructLayout(LayoutKind.Sequential,Pack=4)] public struct Key { public Guid fmtid; public uint pid; public Key(string g,uint p){fmtid=new Guid(g);pid=p;} }
[ComImport,Guid("a1567595-4c2f-4574-a6fa-ecef917b9a40"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)] interface Manager {
 [PreserveSig]int GetDevices([Out,MarshalAs(UnmanagedType.LPArray,ArraySubType=UnmanagedType.LPWStr,SizeParamIndex=1)] string[] ids,ref uint count);
}
[ComImport,Guid("625e2df8-6392-4cf0-9ad1-3cfa5f17775c"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)] interface Device {
 void Open([MarshalAs(UnmanagedType.LPWStr)]string id,Values client);
 void SendCommand(uint flags,IntPtr values,out IntPtr result);
 void Content(out Content content);
}
[ComImport,Guid("6a96ed84-7c73-4480-9938-bf5af477d426"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)] interface Content {
 void EnumObjects(uint flags,[MarshalAs(UnmanagedType.LPWStr)]string parent,IntPtr filter,out ObjectIds ids);
 void Properties(out Properties props);
}
[ComImport,Guid("10ece955-cf41-4728-bfa0-41eedf1bbf19"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)] interface ObjectIds {
 [PreserveSig]int Next(uint count,[MarshalAs(UnmanagedType.LPWStr)]out string id,out uint fetched);
}
[ComImport,Guid("7f6d695c-03df-4439-a809-59266beee3a6"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)] interface Properties {
 void GetSupportedProperties([MarshalAs(UnmanagedType.LPWStr)]string id,out IntPtr keys);
 void GetPropertyAttributes([MarshalAs(UnmanagedType.LPWStr)]string id,ref Key key,out Values attrs);
 void GetValues([MarshalAs(UnmanagedType.LPWStr)]string id,IntPtr keys,out Values values);
}
[ComImport,Guid("6848f6f2-3155-4f86-b6f5-263eeeab3143"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)] interface Values {
 void GetCount(out uint count); void GetAt(uint index,IntPtr key,IntPtr value); void SetValue(ref Key key,IntPtr value); void GetValue(ref Key key,IntPtr value);
 void SetStringValue(ref Key key,[MarshalAs(UnmanagedType.LPWStr)]string value);
 [PreserveSig]int GetStringValue(ref Key key,[MarshalAs(UnmanagedType.LPWStr)]out string value);
 void SetUnsignedIntegerValue(ref Key key,uint value); void GetUnsignedIntegerValue(ref Key key,out uint value);
 void SetSignedIntegerValue(ref Key key,int value);void GetSignedIntegerValue(ref Key key,out int value);
 void SetUnsignedLargeIntegerValue(ref Key key,ulong value);
 [PreserveSig]int GetUnsignedLargeIntegerValue(ref Key key,out ulong value);
}
public class Item {public string Id{get;set;}public string Parent{get;set;}public string Name{get;set;}public string OriginalName{get;set;}public string Path{get;set;}public ulong? Size{get;set;}}
public static class Reader {
 public static string Stage { get; private set; } = "not-started";
 static string g="ef6b490d-5cd8-437a-affc-da8b60ee4a3c";
 static Device device;static Content content;static Properties props;
 static T Create<T>(string clsid){return (T)Activator.CreateInstance(Type.GetTypeFromCLSID(new Guid(clsid)));}
 public static int Connect(){
 Stage="create-manager";var m=Create<Manager>("0af10cec-2ecd-4b92-9581-34f6ae0637f3");uint n=0;Stage="count-devices";Marshal.ThrowExceptionForHR(m.GetDevices(null,ref n));
 if(n==0)throw new Exception("No Windows Portable Device returned");var ids=new string[n];Marshal.ThrowExceptionForHR(m.GetDevices(ids,ref n));
 var apple=ids.Where(x=>x!=null&&x.IndexOf("vid_05ac",StringComparison.OrdinalIgnoreCase)>=0).ToArray();if(apple.Length!=1)throw new Exception("Expected one Apple WPD device; got "+apple.Length);
 Stage="create-client-values";var client=Create<Values>("0c15d503-d017-47ce-9016-7b3f978721cc");var access=new Key("204d9f0c-2292-4080-9f42-40664e70f859",9);client.SetUnsignedIntegerValue(ref access,0x80000000);
 Stage="create-device";device=Create<Device>("f7c0039a-4762-488a-b4b3-760ef9a1ba9b");Stage="open-read-only";device.Open(apple[0],client);Stage="get-content";device.Content(out content);Stage="get-properties";content.Properties(out props);Stage="connected";return (int)n;
 }
 public static Item[] Children(string parent,string prefix){
 content.EnumObjects(0,parent,IntPtr.Zero,out var en);var rows=new List<Item>();
 try{while(true){int hr=en.Next(1,out var id,out uint count);if(hr<0)Marshal.ThrowExceptionForHR(hr);if(count==0)break;
 props.GetValues(id,IntPtr.Zero,out var v);try{var k=new Key(g,4);v.GetStringValue(ref k,out string name);k=new Key(g,12);v.GetStringValue(ref k,out string original);k=new Key(g,11);int sz=v.GetUnsignedLargeIntegerValue(ref k,out ulong size);
 rows.Add(new Item{Id=id,Parent=parent,Name=name,OriginalName=original,Size=sz>=0?(ulong?)size:null,Path=prefix+(name??original??id)});
 }finally{Marshal.ReleaseComObject(v);}}
 }finally{Marshal.ReleaseComObject(en);}return rows.ToArray();
 }
}
}
