# À propos

## Le défi

Le #30DayMapChallenge est un défi cartographique ouvert à tous : une carte par jour pendant tout le mois de novembre, chaque jour sur un thème imposé. Les thèmes et les règles sont publiés sur le [site officiel du défi](https://30daymapchallenge.com/). J'aime me complexifier la vie, donc j'ai ajouté deux contraintes supplémentaires : un seul territoire pour les trente cartes, et un seul prompt par carte.

## Rochefort

Les trente cartes de cette série portent toutes sur Rochefort, en Charente-Maritime. Pourquoi Rochefort ? Pourquoi pas ? Voilà, vous avez votre réponse.

## Une carte, un prompt

Chaque carte de la série est née d'un seul prompt. Je donne le jour, le thème et mon idée ; je ne touche jamais à QGIS. Tout le reste est réalisé par Claude (abonnement payant), connecté à QGIS par le protocole MCP : recherche des données, traitements, mise en page, export.

Pour que cela tienne sur trente jours, j'ai construit une méthode de travail :

- **Un skill**, sorte de mode d'emploi que Claude suit à chaque carte : les étapes, les règles à respecter et les outils à utiliser, toujours dans le même ordre.
- **Une boîte à outils commune** : un gabarit de mise en page au format 4:5, un cache de données ouvertes sur Rochefort (IGN, Insee, OpenStreetMap), une charte graphique, des scripts d'export et de contrôle automatique.
- **Trois agents spécialisés**, qui se passent le relais :
  - l'**Éclaireur** cherche et télécharge les données qui manquent, puis consigne leur source et leur licence ;
  - l'**Exécuteur** construit la carte dans QGIS, de la symbologie à l'export ;
  - le **Vérificateur**, qui n'a pas vu la carte se construire, la juge à froid sur une grille de contrôle : titre, légende, orientation, échelle, sources, lisibilité.
- **Deux allers-retours au maximum** entre l'Exécuteur et le Vérificateur, puis la carte est livrée.

Une fois la carte validée, elle rejoint ce site sans intervention manuelle de ma part. Chaque livraison est consignée dans un fichier de suivi : titre, thème, sources. À partir de ce fichier, une seule commande régénère le site : les images sont optimisées pour le web, la carte prend sa place dans l'atlas des 30 jours, une fiche est créée avec ses sources et ses téléchargements en haute définition, puis le site est publié en ligne. Ce site a lui aussi été conçu avec Claude, dans Claude Code, à partir d'un cahier des charges que j'ai rédigé avec lui.

Ce projet me permet d'approfondir mes connaissances et de comprendre concrètement le fonctionnement des IA : skills, agents, prompts, connecteurs… L'idée de chaque carte reste la mienne. Je m'autorise une reprise uniquement en cas de bug graphique (superposition de textes, de formes, etc.).

## Piloté par l'IA, contrôlé par l'humain

Du calcul des coordonnées géographiques aux géotraitements avancés sous QGIS, chaque avancée technique a réduit le temps nécessaire pour produire une carte fiable. L'arrivée de l'IA générative dans l'écosystème SIG accélère encore ce processus en assistant directement la préparation des données et l'analyse spatiale.

Face à des modèles capables de générer des scripts et des analyses spatiales à la volée, une question pratique se pose : l'IA va-t-elle remplacer le travail cartographique, ou simplement redéfinir le rôle de l'analyste SIG ?

[Voir les 30 jours](../atlas/)