# Leeswijzer

## Inleiding
Elke koppelvlak-specificatie van een register bevat uit dezelfde componenten. Een GraphQL-schema, GraphQL-query specificatie(s), usecases voor raadpleging, toegangscontrole beschrijvingen en functionele beschrijvingen van de notificaties en de autorisatiematrix.

## Raadplegen
Het raadplegen is een dienst die wordt aangeboden door bronhouders aan (toekomstige) afnemers. De volledige beschrijving van deze dienst is te vinden in het [Afsprakenstelsel iWlz > Raadplegen](https://istandaarden.github.io/Afsprakenstelsel-iWlz/current/applicatie/diensten/raadplegen/). 



Hier worden alleen de componenten beschreven die voortkomen uit de koppelvlak-specificatie. 
```mermaid
flowchart RL
    Client(["💻 Client"])

    subgraph Pipeline["Verwerking van het raadpleegverzoek"]
        direction LR
        GQ["GraphQL-query"]
        OPA["🛡️Toegangscontrole"]
        GS["GraphQL-schema <br/>Register"]
        GQ --> OPA --> GS
    end

    DB[("🗄️ Bronhouder Register")]

    Client --> GQ
    GS --> DB

    classDef graphql fill:#f5e6f2,stroke:#E10098,stroke-width:2px,color:#333;
    classDef opa fill:#e6e8eb,stroke:#5b6470,stroke-width:2px,color:#333;
    classDef client fill:#f5f5f5,stroke:#333,stroke-width:2px,color:#333;
    classDef db fill:#d9d9d9,stroke:#555,stroke-width:2px,color:#333;

    class GQ,GS graphql;
    class OPA opa;
    class Client client;
    class DB db;
```
Figuur 1 - Versimpelde weergave van raadplegen

Die componenten die onderdeel zijn van het raadplegen zijn:

| Component                   | type          | Voor wie         |
| :-------------------------- | :------------ | :--------------- |
| GraphQL-schema specificatie | GrapQL-schema | Bronhouder       |
| Raadpleeg use-cases         | Documentatie  | Raadpleger       |
| GraphQL-query template      | GraphQL-query | Raadpleger       |
| Toegangscontrole use-cases  | Documentatie  | Toegangscontrole |
| Autorisatiematrix           | Documentatie  | Toegangscontrole |



## Notificeren
```mermaid
flowchart LR
 subgraph Pipeline["Versturen van de notificatie"]
    direction LR
        GQ["GraphQL-schema <br/>Generiek"]
        OPA["Notificatietype"]
        GS["GraphQL-mutation"]
  end
    GQ --> OPA
    OPA --> GS
    DB[("🗄️ Bronhouder Register")] --> GQ
    GS --> Client(["💻 Client"])

    OPA@{ shape: doc}
     GQ:::graphql
     OPA:::opa
     GS:::graphql
     DB:::db
     Client:::client
    classDef graphql fill:#f5e6f2,stroke:#E10098,stroke-width:2px,color:#333
    classDef opa fill:#e6e8eb,stroke:#5b6470,stroke-width:2px,color:#333
    classDef client fill:#f5f5f5,stroke:#333,stroke-width:2px,color:#333
    classDef db fill:#d9d9d9,stroke:#555,stroke-width:2px,color:#333
```


| Onderdeel                   | type          | Voor wie                |
| :-------------------------- | :------------ | :---------------------- |
| GraphQL-schema specificatie | GrapQL-schema | Bronhouder              |
| Notificaties                | Documentatie  | Bronhouder / Raadpleger |

