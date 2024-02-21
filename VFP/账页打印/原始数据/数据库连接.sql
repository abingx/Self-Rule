SELECT 批库存.册序号, 批库存.货位, COUNT(批库存.可用库存数) AS 数量;
 FROM ;
     dbo.基本库 基本库 ;
    INNER JOIN dbo.批库存 批库存 ;
   ON  基本库.册序号 = 批库存.册序号;
 WHERE  批库存.可用库存数 > ( 0 );
 GROUP BY 批库存.册序号, 批库存.货位;
 ORDER BY 批库存.册序号, 批库存.货位