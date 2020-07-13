//Veison 4.4
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
PB = 1   //课程类型标志：1必修，2选修

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

Function findkeig(keiglwxk) 
    Call findkeywords("查看详情")
    Call findkeywords(keiglwxk)
    If intX > 0 And intY > 0 Then 
        MoveTo intX + 71, intY + 97
        Delay 500
        LeftClick 1
        Goto keigxrze
    Else 
        KeyPress 116, 1
        Delay 10000
        Goto keiglwxk
    End If
End Function

Function yemmpjdr()
	yemmpjdr = 0
	Call findkeywords("所属教学计划")
	If intX > 0 and intY > 0 Then
    	yemmpjdr = 1
	End If 
	Call findkeywords("上课时间")
	If intX > 0 and intY > 0 Then
    	yemmpjdr = 2
	End If 
	Call findkeywords("视频详情")
	If intX > 0 and intY > 0 Then
    	yemmpjdr = 3
	End If 
End Function

Rem Main

Rem keiglwxk
PA = yemmpjdr()
If PA = 0 Then
    KeyPress 116, 1
    Delay 30000
    Goto Main
Elseif PA = 2 Then
    Goto keigxrze
Elseif PA = 3 Then
    Goto xtxijpmm    
End If
If PB = 1 Then
    GJ = "线上课程【必修课】"
Else
    GJ = "线上课程【选修课】"
End If
Call findkeig(GJ)

Rem keigxrze
PA = yemmpjdr()
If PA = 0 Then
    KeyPress 116, 1
    Delay 30000
    Goto Main
Elseif PA = 1 Then
    Goto keiglwxk
Elseif PA = 3 Then
    Goto xtxijpmm    
End If
P = pageloading("视频")
If P = 0 Then
	KeyPress 116, 1  
	Goto keigxrze
End If
Call findkeywords("去学习")
If intX < 0 And intY < 0 Then 
    If PB = 1 Then
        PB = 2
    Else 
        PB = 1
    End If 
    Call backtopage()
    Delay 10000
    Call yemmpjdr()
    Goto keiglwxk
End If
MoveTo intX+5, intY+5
LeftClick 1

Rem xtxijpmm
PA = yemmpjdr()
If PA = 0 Then
    KeyPress 116, 1
    Delay 30000
    Goto Main
Elseif PA = 1 Then
    Goto keiglwxk
Elseif PA = 2 Then
    Goto keigxrze    
End If
P = pageloading("视频加载中")  //偶尔没有出现"视频加载中"
IF P = 1 Then
	KeyPress 116, 1  
	Goto xtxijpmm
Else
	CI = 0
	While CI < 60
    	Delay 60000
    	Call findkeywords("恭喜您")
    	If intX > 0 And intY > 0 Then 
        	MoveTo intX+303,intY+54
        	Delay 500
        	LeftClick 1
        	Delay 1000
        	Call backtopage()
        	Delay 10000
        	Call yemmpjdr()
        	Goto keigxrze
    	End If
    	Call findkeywords("您已完成了")
    	If intX > 0 And intY > 0 Then 
        	MoveTo intX+303,intY+54
        	Delay 500
        	LeftClick 1
        	Delay 1000
        	Call backtopage()
        	Delay 10000
        	Call yemmpjdr()
        	Goto keigxrze
    	End If
    	Call findkeywords("该视频已学习时长")
    	IfColor intX+541, intY-82, "FFFFFF", 0 Then
            Call backtopage()
            Delay 10000
            Call yemmpjdr()
            Goto keigxrze
    	End If
        Call findkeywords("缓冲中")
        If intX > 0 And intY > 0 Then 
            Delay 30000
            Call findkeywords("缓冲中")
            If intX > 0 And intY > 0 Then 
                Call backtopage()
                Delay 10000
                Call yemmpjdr()
                Goto keigxrze
            End If
        End If
    	Delay 500
    	KeyPress "Up", 1
    	CI = CI + 1
	Wend
	Call backtopage()
	Delay 10000
	Call yemmpjdr()
	Goto keigxrze
End If	

Rem endstudy


//todo
//后台运行
