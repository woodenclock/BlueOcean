## Guide for myself (Jonathan)

### Usage commands (in /apps/api)

#### Running the backend service

1. uv run fastapi dev main.py --host 0.0.0.0 --port 8008 (local)
2. uv run fastapi run main.py --host 0.0.0.0 --port XXXX (prod)

---

### POST endpoints

#### POST () ?

### GET endpoints

#### GET (/map)

expect schema (referencing Layout Interchange Format(LIF))

> *https://www.vdma.eu/documents/34570/3317035/FuI_Guideline_LIF_GB.pdf*

returns an array of LIF ? for each of the robots....?

> { "robots":
>
> > [metainformation ...(maybe just isolate the nodes and edges position?)]
> > }

#### GET (/robot_data/{robot_index})

expects schema

> {
> "robot_type" : string (default "kiva" ?),
> "refresh_rate" : int (per second, default "1"),
> }

#### GET (/robot_position/{robot_index})

expects schema (reference VDMA 5050 document?)

> {
> "x\_
> }

### Personal Notes

frontend calls:
fetch("http://localhost:8000/${whatever-route-you-need}")
