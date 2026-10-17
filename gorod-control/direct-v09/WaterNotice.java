package ru.citycontrol.shakhty;

import java.time.*;
import java.util.*;
import java.util.regex.*;

/** Pure Java parser for original public water notices. No network, Android APIs or location upload. */
public final class WaterNotice {
  private static final ZoneOffset MSK=ZoneOffset.ofHours(3);
  private static final String TIME="([01]?\\d|2[0-3])\\s*[:.=\\-]\\s*([0-5]\\d)(?!\\d)";
  private static final String HOUSE="\\d+[а-яa-z]?(?:/\\d+[а-яa-z]?)?(?:\\s*[-–]\\s*\\d+[а-яa-z]?)?";
  private static final String[] MONTHS="января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split(" ");
  private static final String[][] TYPES={{"ул","улица|ул\\.?"},{"пер","переулок|пер\\.?"},{"проспект","проспект|просп\\.?|пр-кт|пр-т|пр\\."},{"проезд","проезд|пр-д"},{"пос","поселок|посёлок|пос\\.?"},{"мкр","микрорайон|мкр\\.?"}};
  private static Pattern re(String s){return Pattern.compile(s,Pattern.CASE_INSENSITIVE|Pattern.UNICODE_CASE);}
  private static String clean(String s){return s.replace('\u00a0',' ').replace("\ufe0f","").replaceAll("[ \\t]+"," ").trim();}
  private static final class DateAt {int a,b;LocalDate d;DateAt(int a,int b,LocalDate d){this.a=a;this.b=b;this.d=d;}}
  private static List<DateAt> dates(String s,int year){
    List<DateAt> out=new ArrayList<>();Matcher m=re("(?<!\\d)([0-3]?\\d)[./]([01]?\\d)[./](20\\d{2}|\\d{2})(?!\\d)").matcher(s);
    while(m.find())try{int y=Integer.parseInt(m.group(3));if(y<100)y+=2000;out.add(new DateAt(m.start(),m.end(),LocalDate.of(y,Integer.parseInt(m.group(2)),Integer.parseInt(m.group(1)))));}catch(Exception ignored){}
    m=re("(?<!\\d)([0-3]?\\d)\\s+("+String.join("|",MONTHS)+")(?:\\s+(20\\d{2}))?").matcher(s);
    while(m.find())try{int mon=Arrays.asList(MONTHS).indexOf(m.group(2).toLowerCase(Locale.ROOT))+1;out.add(new DateAt(m.start(),m.end(),LocalDate.of(m.group(3)==null?year:Integer.parseInt(m.group(3)),mon,Integer.parseInt(m.group(1)))));}catch(Exception ignored){}
    out.sort(Comparator.comparingInt(x->x.a));return out;
  }
  private static LocalDate after(String s,int pos,List<DateAt> dates){
    for(DateAt d:dates)if(d.a>=pos&&d.a-pos<=22&&s.substring(pos,d.a).matches("[\\s.,]*(?:(?:час\\.?|часов|часа)\\s*)?[\\s.,]*"))return d.d;
    return null;
  }
  private static OffsetDateTime at(LocalDate d,String h,String m){return d.atTime(Integer.parseInt(h),Integer.parseInt(m)).atOffset(MSK);}
  public static Map<String,Object> area(String raw){
    String s=clean(raw).replaceFirst("(?iu)^(?:г\\.?\\s*Шахты|Шахты)\\s*,?\\s*","").replaceAll("^[▫▪•✔✅🔹🔸 \\t]+|[ .,;]+$","");
    s=s.replaceFirst("(?iu)\\s+и\\s+прилегающ.*$","");
    List<String> houses=new ArrayList<>();Matcher n=re("^(.*?)\\s*(?:,?\\s+д(?:ом)?\\.?\\s*|,\\s*|\\s+)("+HOUSE+"(?:\\s*,\\s*"+HOUSE+")*)$").matcher(s);
    if(n.matches()){s=n.group(1).replaceAll("[ .,;]+$","");for(String v:n.group(2).split(","))houses.add(v.replaceAll("\\s+","").replace('–','-').toLowerCase(Locale.ROOT));}
    for(String[] t:TYPES){Matcher a=re("^(?:"+t[1]+")\\s*(.+)$").matcher(s),b=re("^(.+?)\\s+(?:"+t[1]+")$").matcher(s);String name=a.matches()?a.group(1):b.matches()?b.group(1):null;
      if(name!=null&&!name.trim().isEmpty()&&name.length()<100){Map<String,Object> out=new LinkedHashMap<>();out.put("street",t[0]+" "+name.trim());out.put("houses",houses);return out;}}
    return null;
  }
  public static Map<String,Object> parse(String url,String input,Instant now,String publishedHint){
    if(url==null||!url.matches("^https://rovodokanal\\.ru/emergency-alerts/\\d+$")||input==null||input.length()>60000)return null;
    String text=clean(input);Matcher branch=re("Филиал\\s+[«\"']?Шахтинский[»\"']?\\s+(?:сообщает|напоминает)").matcher(text);
    if(!branch.find())return null;text=text.substring(branch.start());
    String low=text.toLowerCase(Locale.ROOT);String kind;
    if(re("(?<!не )водоснабжение\\s+восстановлено|работы\\s+завершены|подача воды возобновлена").matcher(low).find())kind="resolved";
    else if(re("работы\\s+продлены|срок.*продлен|перенесены").matcher(low).find())kind="extension";
    else if(re("плановые\\s+работы|плановое\\s+отключение|запланирован|будет\\s+(?:приостановлено|снижено|отключено)").matcher(low).find())kind="planned";
    else if(re("снижение\\s+давления|снижено\\s+давление|отключение воды|аварийно").matcher(low).find())kind="emergency";
    else return null;
    OffsetDateTime published=null;try{published=OffsetDateTime.parse(publishedHint);}catch(Exception ignored){}
    int year=(published==null?now.atOffset(MSK):published).getYear();List<DateAt> ds=dates(text,year);
    Matcher sm=re("\\bс\\s+"+TIME).matcher(text),em=re("(?:\\bдо\\s+|ориентировочн[^\\n]{0,90}?(?:завершения|окончания)[^\\d\\n]{0,18})"+TIME).matcher(text);
    OffsetDateTime start=null,end=null;String basis="unknown";
    if(sm.find()){
      LocalDate d=after(text,sm.end(),ds);if(d==null){for(DateAt x:ds)if(x.b<=sm.start()&&sm.start()-x.b<80)d=x.d;}
      if(d==null&&!ds.isEmpty())d=ds.get(0).d;if(d==null&&published!=null)d=published.toLocalDate();
      if(d!=null){start=at(d,sm.group(1),sm.group(2));basis="explicit";}
    }else if(kind.equals("planned")&&!ds.isEmpty()){start=ds.get(0).d.atStartOfDay().atOffset(MSK);basis="date_only";}
    else if(published!=null){start=published;basis="publication";}
    if(em.find()){
      LocalDate d=after(text,em.end(),ds);boolean explicit=d!=null;
      if(d==null&&start!=null)d=start.toLocalDate();if(d==null&&!ds.isEmpty())d=ds.get(ds.size()-1).d;
      if(d!=null){end=at(d,em.group(1),em.group(2));if(start!=null&&end.isBefore(start)&&!explicit)end=end.plusDays(1);if(start!=null&&end.isBefore(start))end=null;}
    }
    if(start==null)return null;
    if(start.toInstant().isAfter(now.plusSeconds(14*86400))||start.toInstant().isBefore(now.minusSeconds(72*3600)))return null;
    if(end!=null&&end.toInstant().isBefore(now.minusSeconds(24*3600)))return null;
    boolean active=false,partial=false;List<Map<String,Object>> areas=new ArrayList<>();List<String> unknown=new ArrayList<>();
    for(String line:text.split("\\n")){
      line=clean(line).replaceAll("^[▫▪•✔✅🔹🔸🗺 \\t]+","");
      if(re("^Адрес(?:а|ы)?\\s*:").matcher(line).find()){active=true;line=line.substring(line.indexOf(':')+1).trim();}
      if(!active)continue;
      if(re("^(?:Подробност|Подробнее|Ориентировоч|Подвоз|Телефон|Источник|ℹ|🔗)").matcher(line).find())break;
      if(line.isEmpty())continue;
      if(re("прилегающ|частичн|часть|район").matcher(line).find())partial=true;
      Map<String,Object> a=area(line);if(a!=null)areas.add(a);else{unknown.add(line);partial=true;}
    }
    if(areas.isEmpty())return null;
    String id=url.substring(url.lastIndexOf('/')+1);Map<String,Object> e=new LinkedHashMap<>();
    e.put("id","water-oursv-"+id);e.put("category","water");e.put("kind",kind.equals("resolved")||kind.equals("extension")?"emergency":kind);
    String status=kind.equals("resolved")?"resolved":kind.equals("extension")||end!=null&&end.toInstant().isBefore(now)?"unconfirmed":"active";
    e.put("status",status);e.put("sourceId","ursv_device");e.put("source","УРСВ · оригинал с телефона");e.put("origin","official_device");e.put("url",url);e.put("officialUrl",url);
    e.put("publishedAt",published==null?null:published.toString());e.put("observedAt",now.toString());e.put("start",start.toString());e.put("end",end==null?null:end.toString());e.put("startBasis",basis);
    e.put("title",kind.equals("planned")?"Плановые работы водоканала":"Сообщение УРСВ о водоснабжении");e.put("description",text.substring(0,Math.min(400,text.length())).replaceAll("\\s+"," "));
    e.put("fullText",text);e.put("affected",areas);e.put("point",null);e.put("precision","street");e.put("requiresReview",partial||kind.equals("extension"));e.put("unmappedAreaText",unknown);
    return e;
  }
}
