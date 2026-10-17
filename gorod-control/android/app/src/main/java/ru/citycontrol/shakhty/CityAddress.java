package ru.citycontrol.shakhty;

import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Deterministic street and house matcher. Never assumes a street and a lane
 * having the same name are identical. This class has no Android dependencies.
 */
public final class CityAddress {
  private CityAddress() {}

  private static final String[] KINDS={
    "ул","пер","просп","проезд","пл","бул","пос","мкр"
  };
  private static final String[] LEADING={
    "^(?:улица|ул\\.?)\\s+(.+)$",
    "^(?:переулок|пер\\.?)\\s+(.+)$",
    "^(?:проспект|пр-?кт|пр-?т|пр\\.?)\\s+(.+)$",
    "^(?:проезд|пр-д)\\s+(.+)$",
    "^(?:площадь|пл\\.?)\\s+(.+)$",
    "^(?:бульвар|бул\\.?)\\s+(.+)$",
    "^(?:поселок|посёлок|пос\\.?)\\s+(.+)$",
    "^(?:микрорайон|мкр\\.?)\\s+(.+)$"
  };
  private static final String[] TRAILING={
    "^(.+)\\s+(?:улица|ул\\.?)$",
    "^(.+)\\s+(?:переулок|пер\\.?)$",
    "^(.+)\\s+(?:проспект|пр-?кт|пр-?т)$",
    "^(.+)\\s+проезд$",
    "^(.+)\\s+площадь$",
    "^(.+)\\s+бульвар$",
    "^(.+)\\s+(?:поселок|посёлок)$",
    "^(.+)\\s+микрорайон$"
  };
  private static final Pattern[] LEAD_PATTERNS=new Pattern[KINDS.length];
  private static final Pattern[] TAIL_PATTERNS=new Pattern[KINDS.length];
  static {
    for(int i=0;i<KINDS.length;i++){
      LEAD_PATTERNS[i]=Pattern.compile(LEADING[i]);
      TAIL_PATTERNS[i]=Pattern.compile(TRAILING[i]);
    }
  }
  private static String normal(String s){
    return s==null?"":s.toLowerCase(Locale.ROOT).replace('ё','е')
      .replaceAll("\\s+"," ").replaceAll("[«»\"']","").trim();
  }
  public static String street(String raw){
    String s=normal(raw).replaceFirst("^(?:г\\.?\\s*шахты)\\s*,?\\s*","")
      .replaceFirst("\\bдом\\b.*$","").replaceAll("[.,;]+$","").trim();
    if(s.isEmpty())return "";
    for(int i=0;i<KINDS.length;i++){
      Matcher a=LEAD_PATTERNS[i].matcher(s),b=TAIL_PATTERNS[i].matcher(s);
      if(a.matches())return KINDS[i]+":"+a.group(1).replaceAll("[.,;]+$","").trim();
      if(b.matches())return KINDS[i]+":"+b.group(1).replaceAll("[.,;]+$","").trim();
    }
    return "неуточн:"+s;
  }
  public static String house(String raw){
    return normal(raw).replaceFirst("^(?:д(?:ом)?\\.?\\s*)","")
      .replaceAll("\\s+","").replaceAll("[^\\da-zа-я/\\-]","");
  }
  public static boolean houseMatches(String saved,String listing){
    String h=house(saved),t=house(listing);
    if(h.isEmpty()||t.isEmpty())return false;
    if(h.equals(t))return true;
    Matcher bounds=Pattern.compile("^(\\d+)-(\\d+)$").matcher(t);
    Matcher homeNumber=Pattern.compile("^(\\d+)").matcher(h);
    if(!bounds.matches()||!homeNumber.find())return false;
    try{
      int a=Integer.parseInt(bounds.group(1)),
          b=Integer.parseInt(bounds.group(2)),
          n=Integer.parseInt(homeNumber.group(1));
      return n>=Math.min(a,b)&&n<=Math.max(a,b)
          &&(a%2!=b%2||n%2==a%2);
    }catch(NumberFormatException ex){return false;}
  }
}
