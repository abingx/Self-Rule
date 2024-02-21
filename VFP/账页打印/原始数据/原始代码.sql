&&
&&以上为数据库连接部分
&&以下为表格筛选过程
&&ALTER  TABLE jg (册序号 c(6),货位1 c(8),数量1 n(10,3))
SET SAFETY OFF 
CREATE TABLE jg (册序号 c(6),货位00 c(8),数量00 n(10,3))
USE jg
DELETE ALL
PACK
PUBLIC p,i,hw,sl,j,h
i=2
USE jg
append blank
GO 1
USE kc
GO 1
SCATTER MEMVAR
p=m.册序号
USE jg
replace 册序号 WITH m.册序号
replace 货位00 WITH m.货位
replace 数量00 WITH m.数量
USE kc
GO 1
SKIP 1
IF EOF()
   ELSE
   GO i 
   DO WHILE .t. 
      SCATTER MEMVAR      
      IF p=m.册序号 
         j=j+1
         IF j>9
            h=h+1
            j=0
         ENDIF   
         hw='货位'+STR(h,1,0)+STR(j,1,0)
         sl='数量'+STR(h,1,0)+STR(j,1,0)
         USE jg
         IF fsize("&hw")=0    &&判断是否存在该字段
            ALTER table jg ADD &hw c(8)
            ALTER table jg ADD &sl n(10,3)
         ENDIF
         GO BOTTOM 
         replace &hw WITH m.货位
         replace &sl WITH m.数量
         USE kc
         GO i
         SKIP 1
         IF EOF()
            EXIT
         ENDIF 
         i=i+1
         GO i
      ELSE 
         USE jg
         append blank
         GO BOTTOM 
         replace 册序号 WITH m.册序号
         replace 货位00 WITH m.货位
         replace 数量00 WITH m.数量
         USE kc
         GO i
         SKIP 1
         IF EOF()
            EXIT
         ENDIF 
         i=i+1
         GO i
         p=m.册序号
         j=0
         h=0
         ENDIF
      ENDDO
ENDIF 
&&jg表格需连接基本库，之后补上
&&以上为数据筛选部分
&&以下为输出打印部分



