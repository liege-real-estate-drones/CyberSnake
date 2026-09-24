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
| Désinstaller | `bash /userdata/system/borne_manettes/install.sh --uninstall` |
