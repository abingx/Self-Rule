//veison 2.0
Dim MyArray   //定义变量，用于获取窗口大小
Dim x1, y1, x2, y2   //定义窗口坐标变量
Dim intX, intY    //定义坐标变量
Hwnd = Plugin.Window.Find("Chrome_WidgetWin_1", "蓉城先锋·党员e家")   //查找挂机窗口
Call Plugin.Window.Active(Hwnd)  //激活挂机窗口
sRect = Plugin.Window.GetClientRect(Hwnd)  //获取窗口大小
MyArray = Split(sRect, "|")  //分离窗口大小数组
x1 = Clng(MyArray(0))   //窗口左上X
y1 = Clng(MyArray(1))   //窗口左上y
x2 = Clng(MyArray(2))   //窗口右下X
y2 = Clng(MyArray(3))   //窗口右下y

Function pageloading( ) //页面是否完成加载，需修改
    GetColor=GetPixelColor(x1+10,y1+67)
    IfColor x1+10,y1+67,"FFFFFF",0 Then  
    Else
    End If 
End Function

Function findkeywords(keywords) //获取关键字坐标
    KeyPress "Esc", 1
    KeyDown 17, 1
    KeyPress 70, 1
    KeyUp 17, 1
    Delay 300
    SayString keywords
    Delay 500
    FindColor x1, y1, x2, y2, "3296FF", intX, intY
    Delay 100
    KeyPress "Esc", 1
End Function

Function findkeig(keigxrze) //暂未使用，下一步优化时使用
    findkeywords(keigxrze)
    If intX > 0 And intY > 0 Then 
        MoveTo intX + 71, intY + 97
        Delay 500
        LeftClick 1
    Else 
        //刷新页面
    End If
End Function

Function backtopage() //返回上一页
    MoveTo x1+20, y1+17
    LeftClick 1
    Delay 10000
End Function


Rem quxuexi  //标记
Delay 5000
findkeywords("去学习")
If intX < 0 And intY < 0 Then 
    Delay 10000
    Goto quxuexi
    //call backtopage()
    //Goto endstudy
EndIf
MoveTo intX+5, intY+5
LeftClick 1
Delay 500
While True
    Delay 60000
    findkeywords("恭喜您")
    If intX > 0 And intY > 0 Then 
        MoveTo intX+303,intY+54
        Delay 500
        LeftClick 1
        Delay 500
        call backtopage()
        Delay 10000
        Goto quxuexi
    End If
    findkeywords("该视频已学习时长")
    IfColor intX+90, intY-83, "FFFFFF", 0 Then
        call backtopage()
        Delay 10000
        Goto quxuexi
    End If
    Delay 500
    KeyPress "Up", 1
Wend

Rem endstudy


//done
//自定义函数运行 
//todo
//判断页面是否完成加载 
//多页面执行
//后台运行
