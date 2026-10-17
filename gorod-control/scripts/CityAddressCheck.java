import ru.citycontrol.shakhty.CityAddress;

public final class CityAddressCheck {
  private static int cases=0;
  private static void check(boolean ok,String label){
    cases++;
    if(!ok)throw new IllegalStateException("Address matching failure: "+label);
  }
  public static void main(String[] args){
    check(CityAddress.street("ул. Шишкина").equals(CityAddress.street("улица Шишкина")),"street aliases");
    check(!CityAddress.street("ул. Шишкина").equals(CityAddress.street("пер. Шишкина")),"street is not lane");
    check(!CityAddress.street("ул. Шишкина").equals(CityAddress.street("проезд Шишкина")),"street is not driveway");
    check(CityAddress.street("пр-кт Красной Армии").equals(CityAddress.street("проспект Красной Армии")),"avenue aliases");
    check(CityAddress.street("Советская улица").equals(CityAddress.street("ул Советская")),"reverse geocoder style");
    check(CityAddress.street("ул Юный Спартак").equals(CityAddress.street("г Шахты, улица Юный Спартак")),"full city prefix");
    check(CityAddress.street("Советская").startsWith("неуточн:"),"unknown type not guessed");
    check(CityAddress.house("д. 183А").equals(CityAddress.house("183а")),"house letter");
    check(CityAddress.houseMatches("11","1-49"),"odd range matches");
    check(!CityAddress.houseMatches("12","1-49"),"even house excluded");
    check(CityAddress.houseMatches("12","10-20"),"mixed parity numeric range");
    check(!CityAddress.houseMatches("22","10-20"),"outside range");
    check(!CityAddress.houseMatches("15","11"),"unrelated house");
    check(CityAddress.houseMatches("д. 183А","183а"),"exact compound house");
    System.out.println("Android address checker OK: "+cases+" cases");
  }
}
