import ru.citycontrol.shakhty.WaterNotice;
import java.time.*;
import java.util.*;
public final class NativeNoticeCheck {
 static int n=0;static void check(boolean b,String s){n++;if(!b)throw new AssertionError(s);}
 static final String URL="https://rovodokanal.ru/emergency-alerts/1591";
 static final Instant NOW=Instant.parse("2026-10-17T10:00:00Z");
 static final String BODY="Филиал \"Шахтинский\" сообщает:\nСнижение давления\nПричина\nВ связи с аварийно-ремонтными работами по адресу пер. Шишкина д. 183А с 09-30 час. 17.10.2026\nАдреса:\nг Шахты, ул Юный Спартак\nг Шахты, пер Шишкина\nг Шахты, ул Советская 11\nПодробности\nОриентировочное время завершения работ 18-00 час. 17.10.2026";
 public static void main(String[] args){
  Map<String,Object> e=WaterNotice.parse(URL,BODY,NOW,null);check(e!=null,"real-style original parsed");
  check(e.get("start").equals("2026-10-17T09:30+03:00"),"explicit start, no fabricated seconds");
  check(e.get("end").equals("2026-10-17T18:00+03:00"),"explicit end");
  check(e.get("publishedAt")==null,"retrieval time is not publication time");
  check(e.get("status").equals("active"),"active interval");
  check(((List<?>)e.get("affected")).size()==3,"only affected addresses");
  check(WaterNotice.parse("https://evil.example/emergency-alerts/1591",BODY,NOW,null)==null,"wrong origin rejected");
  check(WaterNotice.parse(URL,BODY.replace("Шахтинский","Азовский"),NOW,null)==null,"different branch rejected");
  check(WaterNotice.parse(URL,BODY,Instant.parse("2026-10-24T10:00:00Z"),null)==null,"old event never current");
  e=WaterNotice.parse(URL,BODY,NOW.plusSeconds(12*3600),null);check(e.get("status").equals("unconfirmed"),"overdue is not restored");
  Map<String,Object> a=WaterNotice.area("Туркменский пер, д 23");check(a!=null&&a.get("street").equals("пер Туркменский"),"suffix lane preserved");
  check(((List<?>)a.get("houses")).get(0).equals("23"),"suffix address house preserved");
  check(WaterNotice.area("ул. Шишкина").get("street").equals("ул Шишкина"),"lane and street distinct");
  String plan="Филиал \"Шахтинский\" сообщает:\nПлановые работы\n17.10.2026 с 08:00 до 08:00 20.10.2026\nАдреса:\nул. Советская 11\nПодробности";
  e=WaterNotice.parse(URL,plan,NOW,null);check(e!=null,"multiday parsed");
  check(Duration.between(OffsetDateTime.parse((String)e.get("start")),OffsetDateTime.parse((String)e.get("end"))).toHours()==72,"72-hour planned interval");
  String unknown="Филиал \"Шахтинский\" сообщает:\nСнижение давления\nАдреса:\nул. Советская 11\nПодробности";
  check(WaterNotice.parse(URL,unknown,NOW,null)==null,"no invented event date");
  System.out.println("NATIVE ORIGINAL NOTICE CHECKS PASSED: "+n);
 }
}
