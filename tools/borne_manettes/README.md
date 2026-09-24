# Borne Manettes : J1 / J2 toujours à la même place (tous les jeux Batocera)

**Le problème :** les deux encodeurs « Zero Delay » (DragonRise) du kit EG STARTS sont
identiques : même nom, même identifiant, pas de numéro de série. Batocera les numérote
dans l'ordre où ils répondent au démarrage, donc au hasard. Changer de port USB n'y change rien.

**La solution :** un service reconnaît chaque encodeur par son **port USB**, le capture et
le remplace par une manette virtuelle au nom unique (**Borne J1** / **Borne J2**). Le sens
de chaque stick est corrigé au passage, pour tous les jeux.

## Installation (en SSH sur la borne : `ssh root@batocera.local`, mot de passe `linux`)

```
curl -L https://raw.githubusercontent.com/liege-real-estate-drones/CyberSnake/main/tools/borne_manettes/install.sh | bash
```

L'assistant demande à J1 puis à J2 de pousser son stick vers le haut puis vers la droite.
Ensuite, dans EmulationStation :

1. Menu > Réglages des manettes > Configurer une manette : configurer **Borne J1**, puis **Borne J2**.
2. Même menu : Joueur 1 = **Borne J1**, Joueur 2 = **Borne J2**.

Ne plus déplacer les câbles USB des encodeurs après l'installation (sinon relancer l'assistant).

## Commandes utiles

| Action | Commande |
|---|---|
| Voir les périphériques | `python3 /userdata/system/borne_manettes/borne_manettes.py --list` |
| Refaire l'assistant | `/userdata/system/services/borne_manettes stop` puis `python3 /userdata/system/borne_manettes/borne_manettes.py --learn` puis `/userdata/system/services/borne_manettes start` |
| Journal | `cat /userdata/system/logs/borne_manettes.log` |
| Désinstaller | `bash /userdata/system/borne_manettes/install.sh --uninstall` |
