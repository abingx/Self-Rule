//Veison 3.2
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

Function pageloading(loadingkeywords) //页面是否完成加载，返回值1为未正常加载
	Delay 30000
	Call findkeywords(loadingkeywords)
    If intX > 0 and intY > 0 Then
    	pageloading = 1
    Else	
    	pageloading = 0
    End If
End Function

Function backtopage() //返回上一页
    MoveTo x1+20, y1+17
    LeftClick 1
    Delay 10000
End Function

Rem quxuexi  //标记
Delay 500
Call findkeywords("去学习")
If intX < 0 And intY < 0 Then 
    P = pageloading("视频")
    If P Then
    	KeyPress 116, 1  
    	Delay 30000
    	Goto quxuexi
    Else 
    	Goto quxuexi
	End If
End If

MoveTo intX+5, intY+5
LeftClick 1
P = pageloading("视频加载中")
IF P Then
	Call backtopage()
	Delay 10000
	goto quxuexi
Else
	While True
    	Delay 60000
    	Call findkeywords("恭喜您")
    	If intX > 0 And intY > 0 Then 
        	MoveTo intX+303,intY+54
        	Delay 500
        	LeftClick 1
        	Delay 1000
        	Call backtopage()
        	Delay 10000
        	Goto quxuexi
    	End If
    	Call findkeywords("该视频已学习时长")
    	IfColor intX+90, intY-83, "FFFFFF", 0 Then
            Call backtopage()
            Delay 10000
            Goto quxuexi
    	End If
        Call findkeywords("缓冲中")
        If intX > 0 And intY > 0 Then 
            Delay 30000
            Call findkeywords("缓冲中")
            If intX > 0 And intY > 0 Then 
                Call backtopage()
                Delay 10000
                Goto quxuexi
            End If
        End If
    	Delay 500
    	KeyPress "Up", 1
	Wend
End If	

Rem endstudy


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
//done
//自定义函数运行 
//todo
//多页面执行
//后台运行


//判断页面执行相应内容
//课程目录
//视频详情