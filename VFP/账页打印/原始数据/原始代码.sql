&&
&&����Ϊ���ݿ����Ӳ���
&&����Ϊ���ɸѡ����
&&ALTER  TABLE jg (����� c(6),��λ1 c(8),����1 n(10,3))
SET SAFETY OFF 
CREATE TABLE jg (����� c(6),��λ00 c(8),����00 n(10,3))
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
p=m.�����
USE jg
replace ����� WITH m.�����
replace ��λ00 WITH m.��λ
replace ����00 WITH m.����
USE kc
GO 1
SKIP 1
IF EOF()
   ELSE
   GO i 
   DO WHILE .t. 
      SCATTER MEMVAR      
      IF p=m.����� 
         j=j+1
         IF j>9
            h=h+1
            j=0
         ENDIF   
         hw='��λ'+STR(h,1,0)+STR(j,1,0)
         sl='����'+STR(h,1,0)+STR(j,1,0)
         USE jg
         IF fsize("&hw")=0    &&�ж��Ƿ���ڸ��ֶ�
            ALTER table jg ADD &hw c(8)
            ALTER table jg ADD &sl n(10,3)
         ENDIF
         GO BOTTOM 
         replace &hw WITH m.��λ
         replace &sl WITH m.����
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
         replace ����� WITH m.�����
         replace ��λ00 WITH m.��λ
         replace ����00 WITH m.����
         USE kc
         GO i
         SKIP 1
         IF EOF()
            EXIT
         ENDIF 
         i=i+1
         GO i
         p=m.�����
         j=0
         h=0
         ENDIF
      ENDDO
ENDIF 
&&jg��������ӻ����⣬֮����
&&����Ϊ����ɸѡ����
&&����Ϊ�����ӡ����



