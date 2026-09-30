"""Single bounded entry point shared by the registry and direct UI."""
from threading import Lock
from threadpoolctl import threadpool_limits
from .data_preparation_tool import prepare, infer_task, Unsuitable, friendly
from .prediction_tool import predict
from .discovery_tool import discover
from utils.serialization import clean

ML_TOOLS={'ml_suitability','regression','classification','clustering','anomaly_detection','feature_importance','model_evaluation'}
_lock=Lock()


def unavailable(task,message,target=None):
    return {'kind':'ml','task':task,'target':target,'suitable':False,'title':'More information is needed','summary':message,'takeaway':'Choose another outcome or upload more suitable records.','reliability':'No model was trained for this result.','warnings':[],'factors':[],'charts':[],'groups':[],'records':[],'technical':{},'facts':[message],'suggestions':['Show the dataset column names.','Summarize the dataset.']}


def run_ml(name,df,types,columns):
    if not _lock.acquire(blocking=False):
        return unavailable(name,'Another prediction experiment is running. Please try again when it finishes.')
    try:
        with threadpool_limits(limits=1):
            task=name
            if name in ('feature_importance','model_evaluation','ml_suitability'):
                if not columns: raise Unsuitable('Choose a column to predict first.')
                task=infer_task(df,types,columns[0])
            if name=='ml_suitability':
                b=prepare(df,types,task,columns)
                title=f"Your data contains enough usable information to try predicting {friendly(b['target'])}."
                result={'kind':'ml','task':'ml_suitability','target':b['target'],'suitable':True,'title':'Checking your data','summary':title,'takeaway':'The next step is to test prediction methods on separate records. Suitability alone does not guarantee useful predictions.','reliability':'No model has been evaluated yet.','warnings':b['warnings'],'factors':[],'charts':[],'groups':[],'records':[],'technical':{'features':b['features'],'excluded':b['excluded'],'train_rows':len(b['train_idx']),'test_rows':len(b['test_idx']),'split':b['split']},'facts':[title],'suggestions':[f"Predict {b['target']}.",f"What matters most for predicting {b['target']}?"]}
            elif task in ('regression','classification'): result=predict(df,types,task,columns)
            else: result=discover(df,types,task,columns)
            return clean(result)
    except Unsuitable as error:
        return unavailable(name,str(error),columns[0] if columns else None)
    except (ValueError,TypeError,OverflowError):
        return unavailable(name,'These inputs could not support this experiment. Try fewer columns, more records, or another outcome.',columns[0] if columns else None)
    finally:
        _lock.release()
