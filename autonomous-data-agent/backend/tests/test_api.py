import io
import json
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from main import app
from services import storage

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "UPLOADS", tmp_path)
    return TestClient(app)

def sample():
    df = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=20).strftime("%Y-%m-%d"), "value": list(range(19))+[1000], "hours": [v*2 for v in range(20)], "team": ["Alpha"]*10+["Beta"]*10, "active": [True,False]*10, "constant": ["fixed"]*20})
    df.loc[2,"team"] = None
    return pd.concat([df,df.iloc[[0]]],ignore_index=True)

@pytest.mark.parametrize("extension", ["csv", "xlsx"])
def test_complete_workflow(client, extension):
    df=sample()
    content=io.BytesIO()
    if extension=="csv": content.write(df.to_csv(index=False).encode())
    else: df.to_excel(content,index=False)
    response=client.post("/api/upload",files={"file":(f"sample.{extension}",content.getvalue())})
    assert response.status_code==201, response.text
    overview=response.json()
    assert overview["rows"]==21 and overview["columns"]==6
    assert overview["type_counts"]=={"numerical":2,"categorical":2,"datetime":1,"boolean":1}
    base=f"/api/dataset/{overview['dataset_id']}"
    quality=client.get(base+"/quality").json()
    assert quality["duplicates"]==1
    assert sum(c["count"] for c in quality["missing"])==1
    assert quality["outlier_count"]==1
    assert quality["constant_columns"]==["constant"]
    expected=round(100*(1-.5/126-.3/21-.2/42),1)
    assert quality["score"]==expected
    stats=client.get(base+"/statistics").json()
    value=next(s for s in stats if s["column"]=="value")
    assert value["mean"]==pytest.approx(df.value.mean())
    assert value["median"]==df.value.median()
    assert value["std"]==pytest.approx(df.value.std())
    assert value["p25"]==df.value.quantile(.25)
    assert len(client.get(base+"/preview").json()["rows"])==20
    charts=client.get(base+"/visualizations").json()
    assert {c["kind"] for c in charts}=={"histogram","bar","line","scatter"}
    assert sum(c["y"] for c in charts[0]["data"])==21
    assert client.get(base+"/correlations").json()["matrix"][0][1]==pytest.approx(df.value.corr(df.hours))
    # New API client, no process-local dataset state needed.
    assert TestClient(app).get(base+"/overview").json()==overview
    assert len(list(storage.UPLOADS.glob("*.json")))==1

@pytest.mark.parametrize("name,content,status",[("bad.txt",b"a,b\n1,2",415),("empty.csv",b"",422),("header.csv",b"a,b\n",422),("bad.csv",b"a,b\n1,2,3",422),("duplicate.csv",b"a,a\n1,2",422),("bad.xlsx",b"not excel",422),("binary.csv",b"\xff\xfe",422),("null.csv",b"a,b\n,",422)])
def test_invalid_uploads(client,name,content,status):
    assert client.post("/api/upload",files={"file":(name,content)}).status_code==status

def test_limits_and_ids(client,monkeypatch):
    assert client.get("/api/health").json()["status"]=="ok"
    assert client.get("/api/dataset/not-an-id/overview").status_code==404
    assert client.get("/api/dataset/00000000-0000-0000-0000-000000000000/overview").status_code==404
    monkeypatch.setattr(storage,"MAX_ROWS",2)
    assert client.post("/api/upload",files={"file":("large.csv",b"a\n1\n2\n3")}).status_code==422
    assert client.post("/api/upload",files={"file":("large.csv",b"x"*(25*1024*1024+1))}).status_code==413

def test_small_constant_and_missing(client):
    response=client.post("/api/upload",files={"file":("small.csv",b"date,a,b,empty\n2026-01-01,1,2,\n")})
    assert response.status_code==201,response.text
    base="/api/dataset/"+response.json()["dataset_id"]
    assert client.get(base+"/correlations").json()["matrix"][0][0] is None
    assert client.get(base+"/statistics").json()[1]["std"] is None

def test_safe_filename(client):
    r=client.post("/api/upload",files={"file":("../../unsafe.csv",b"x\n1\n2")})
    assert r.status_code==201
    assert r.json()["filename"]=="unsafe.csv"
