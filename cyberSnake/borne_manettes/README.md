# Borne Manettes : J1 / J2 toujours à la même place (tous les jeux Batocera)

**Le problème :** les deux encodeurs « Zero Delay » (DragonRise) du kit EG STARTS sont
identiques : même nom, même identifiant, pas de numéro de série. Batocera les numérote
dans l'ordre où ils répondent au démarrage, donc au hasard. Changer de port USB n'y change rien.

**La solution :** un service reconnaît chaque encodeur par son **port USB**, le capture, le
cache aux jeux et le remplace par une **copie conforme** (même nom, mêmes identifiants), créée
toujours dans l'ordre J1 puis J2. Le réglage de boutons de Batocera reste valable : rien à
reconfigurer.

**URGENCE :** si les sticks ne répondent plus, tenir **Select + Start** (J1 ou J2) pendant
**5 secondes** : la correction se désactive et les sticks d'origine reviennent.

**Démarrage anticipé :** le service est lancé par `/boot/boot-custom.sh` dès que `/userdata`
est monté, environ 10 s AVANT EmulationStation. Un jeu lancé au démarrage de la borne
(`global.bootgame`) voit donc déjà les bons J1 / J2. Batocera le relance aussi plus tard
(menu Services) : ce second lancement ne fait rien si tout tourne déjà.

## Pistolets Sinden J1 / J2

**Le problème :** Batocera crée un « Sinden lightgun » par pistolet dans l'ordre où ils
répondent au démarrage (pistolet 1 au hasard). Et si les deux pistolets ont la même caméra
(ex. deux `SindenCamC`), chaque pilote prend la première caméra de ce nom : un pistolet
peut viser avec la caméra de l'autre.

**La solution (`borne_pistolets.py`, lancé par le même service) :** chaque pilote reçoit la
caméra de SON pistolet (réglage `VideoDevice`, trouvée par le câblage USB), puis les
pistolets sont recréés dans l'ordre J1, J2 (liens `/dev/input/borne-pistolet-j1` / `-j2`).
Si Batocera les recrée (pistolet rebranché, réglage modifié), l'ordre est remis, jamais
pendant un jeu.

Choisir le pistolet J1 (active la correction) :
`python3 /userdata/system/borne_manettes/borne_pistolets.py --j1 bleu` (ou `rouge`)

## Installation la plus simple : depuis CyberSnake

Options > Contrôles > **Fixer J1 / J2 pour TOUS les jeux** : J1 puis J2 poussent leur stick
vers le haut puis vers la droite, c'est installé.

Le jeu écrit aussi la liste des périphériques dans
`\\BATOCERA\share\system\logs\cybersnake_peripheriques.txt` (lisible depuis Windows).

## Installation en SSH (alternative)

Sur la borne : `ssh root@batocera.local`, mot de passe `linux` (rien ne s'affiche quand on tape le mot de passe, c'est normal).

```
curl -L https://raw.githubusercontent.com/liege-real-estate-drones/CyberSnake/main/cyberSnake/borne_manettes/install.sh | bash
```

L'assistant demande à J1 puis à J2 de pousser son stick vers le haut puis vers la droite.
Redémarrer ensuite la borne.

Ne plus déplacer les câbles USB des encodeurs après l'installation (sinon relancer l'assistant).

## Commandes utiles

| Action | Commande |
|---|---|
| Voir les périphériques | `python3 /userdata/system/borne_manettes/borne_manettes.py --list` |
| Refaire l'assistant | `/userdata/system/services/borne_manettes stop` puis `python3 /userdata/system/borne_manettes/borne_manettes.py --learn` puis `/userdata/system/services/borne_manettes start` |
| Journal | `cat /userdata/system/logs/borne_manettes.log` |
| Voir les pistolets (caméra, ordre) | `python3 /userdata/system/borne_manettes/borne_pistolets.py --list` |
| Journal des pistolets | `cat /userdata/system/logs/borne_pistolets.log` |
| Désinstaller | `bash /userdata/system/borne_manettes/install.sh --uninstall` |
