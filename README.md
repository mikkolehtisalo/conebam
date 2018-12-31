# Sisällönsuodatus luonnollisen kielen analyysillä

Kiinnosti kokeilla toimisiko luonnollisen kielen analyysi webbi-sivujen sisällönsuodatuksessa. Niinpä väkästelin pienen [python-sovelluksen](github.com/mikkolehtisalo/conebam), joka laajentaa välityspalvelinta suodatusominaisuuksilla. Sisältötyypit tunnistaa [Googlen luonnollisen kielen analyysin palvelu](https://cloud.google.com/natural-language/docs/).

Arkkitehtuurikuvatus:

![Arkkitehtuuri](https://github.com/mikkolehtisalo/conebam/raw/master/architecture.png "Arkkitehtuuri")

Kirjailin ylös joitakin muistiinpanoja. Alempaa löytyy myös screenshotteja sovelluksesta tositoimissa. 

## Polkaise jalkaa tästä se alkaa

Lähtötilassa käytössä on oltava ICAP-protokollaa tukeva proxy-palvelin. Käytin kehityksen aikana [squidia](http://www.squid-cache.org/), konffasin käyttöön myös [TLS:n purkamisen](https://wiki.squid-cache.org/Features/SslPeekAndSplice) ja lisäsin proxy-asetukset valmiiksi selaimeen. 

Lisätään squidin asetuksiin (*/etc/squid/squid.conf*) ICAP-suodattimen kutsuminen.

```
icap_enable on
icap_preview_enable off
icap_service service_resp respmod_precache icap://<palvelimen-osoite>:13440/conebam
adaptation_access service_resp allow all
```

Asennetaan tarpeelliset python-paketit.

```
pip3 install --upgrade pyicap
pip3 install --upgrade beautifulsoup4
pip3 install --upgrade google-cloud-language
```

Haetaan varsinainen suodatusohjelma.

```
git clone https://github.com/mikkolehtisalo/conebam.git
```

## Pilveen lomps

Googlen pilvirajapintojen kutsumista varten on [perustettava avaimet uudelle projektille](https://console.cloud.google.com/projectselector/apis/credentials/serviceaccountkey?pli=1&supportedpurview=project). Tämän jälkeen projektiin on lisättävä ja kytkettävä päälle [Cloud Natural Language API](https://console.cloud.google.com/apis/api/language.googleapis.com/overview?project=conebam).

Tällä hetkellä 30 000 luokittelukyselyä kuukaudessa on ilmaista ja sen jälkeenkin kustannustaso on [varsin maltillinen](https://cloud.google.com/natural-language/pricing). Keskisuuren yrityksen sisällönsuodatus tulisi tällä tekniikalla maksamaan todennäköisesti joitakin kymmeniä tai satoja euroja kuukaudessa.

## Potkitaan rengasta

Säädetään server.py -skriptistä suodatettavat sisältötyypit raja-arvoineen.

```
# As per https://cloud.google.com/natural-language/docs/categories
BLOCKED_CATEGORIES = {
    "/Adult": 0.7,
    "/Sports": 0.7
}
```

Suodatusohjelma käynnistetään antamalla Googlen rajapinnan avaimet ympäristömuuttujalla ja käynnistämällä python-skripti.

```
GOOGLE_APPLICATION_CREDENTIALS=/Users/mikkolehtisalo/google.json python3 server.py
```

Tämän jälkeen kokeillaan suodatusta proxyn lävitse. Sivusto bbc.co.uk/news toimii vielä, koska se on uutissivusto:

![bbc.co.uk/news](https://github.com/mikkolehtisalo/conebam/raw/master/bbc1.png "bbc.co.uk/news")

Urheilu-uutisten etusivu ei vielä laukaise suodatusta, todennäköisesti koska sivulla on paljon muutakin uutisiin liittyvää sisältöä.

![https://www.bbc.com/sport](https://github.com/mikkolehtisalo/conebam/raw/master/bbc1.png "https://www.bbc.com/sport")

Nyrkkeilyä koskeva uutinen on jo selvästi urheilua ja estetty.

![https://www.bbc.com/sport/boxing/46724047](https://github.com/mikkolehtisalo/conebam/raw/master/bbc3.png "https://www.bbc.com/sport/boxing/46724047")

Hei sehän toimii.

## Puutteita, jatkokehitysideoita, ajatuksia

Suodatussovellus on lähes tuotantokelpoinen.

Googlen luokittelija tukee vain englantia. Valmiita luokittelijoita on  saatavilla yleisimmin puhutuille kielille. En löytänyt netistä valmiiksi opetettua suomea tukevaa luokittelijaa. Sellaisen kehittäminen riittävän hyvälaatuiseksi vaatisi todennäköisesti useita viikkoja tai kuukausia työtä. 

Toisaalta suurin osa suodatustuotteista perustuu pitkälti domain-nimien maineeseen, eikä tarkista jokaisen sivun sisältöä. Tästä syystä esim. blogi-palveluissa sijaitseva aikuisviihde useimmiten läpäisee suodatuksen. (Kuulin vain huhua siis kavereilta, en ole koskaan kokeillut.) Sivukohtaisessa suodatuksessa on sekä hyvät että huonot puolensa. Lopulta molemmat tavat suodattaa ovat nykytekniikalla melko tasavertaisia.

Joukkoistamalla olisi aika helppoa kerätä palautetta väärin tunnistetuista sivuista ja tuottaa tietoa, jonka avulla suodatuksen laatua voitaisiin parantaa. Esimerkiksi pienen selaimen lisäosan kehittäminen ei olisi kovinkaan paha nakki. Suurempi työ olisi palautteen käsittelyssä ja liittämisessä valmiiden luokittelijoiden tuottamiin tuloksiin.

Luokittelija vastaa pilvestä n. 1-2 sekunnissa. Pienillä kyselymäärillä se tuskin aiheuttaa ongelmia, mutta käytön asteen kasvaessa yhtäaikaisia kyselyjä voi olla meneillään paljon. Se tarkoittaa yhtäaikaisesti suurta määrää avoimia yhteyksiä, mikä voi joissain ympäristöissä aiheuttaa ongelmia. Sovellusta on mahdollista optimoida esimerkiksi lisäämällä luokittelijaan paikallinen välimuisti.

Sisällön siirtäminen pilvipalveluun on usein kyseenalaista. Julkiset sivut eivät muodosta ongelmaa, mutta joillakin sivuilla on henkilötietoja. Hyvä esimerkki tästä voisi olla esim. verkkopankin käyttöliittymä. Suodatusmoottorin ei pitäisi käsitellä esimerkiksi tunnettujen pankkien käyttöliittymiä. Tämä rajaus on mahdollista tehdä joko squid:n asetuksissa tai jatkokehittämällä sovellusta. Toisaalta käytin pilvestä saatavilla olevaa luokittelijaa lähinnä laiskuuden vuoksi. On premises on tarvittaessa myös mahdollista, mutta Googlelta luokittelijaa ei silloin saa.

En jaksanut paketoida tai dokumentoida sovellusta sen kummemmin. Sovelluksen viimeistely julkaistavaksi esim. pypiin tai rpm-paketiksi ei olisi kovinkaan kummoinen työ. Myös systemd-palvelu olisi kiva pieni lisä.
