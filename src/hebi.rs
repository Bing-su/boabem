use std::cell::RefCell;
use std::collections::HashMap;
use std::panic::catch_unwind;
use std::path::PathBuf;
use std::rc::Rc;

use boa_engine::builtins::promise::{OperationType, Promise, PromiseState};
use boa_engine::context::HostHooks;
use boa_engine::object::builtins::JsPromise;
use boa_engine::value::TryFromJs;
use boa_engine::{Context, JsError, JsObject, JsResult, JsValue, JsVariant, Source};
use num_bigint::BigInt;
use num_traits::Num;
use pyo3::IntoPyObjectExt;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyNone};

#[pyclass(name = "Undefined", module = "boabem.boabem", str, eq, frozen)]
#[derive(Debug, PartialEq)]
pub struct PyUndefined {}

#[pymethods]
impl PyUndefined {
    #[new]
    fn py_new() -> Self {
        Self::new()
    }

    fn __repr__(&self) -> &str {
        "Undefined"
    }
}

impl PyUndefined {
    pub fn new() -> Self {
        Self {}
    }
}

impl std::fmt::Display for PyUndefined {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "undefined")
    }
}

#[pyclass(name = "Context", module = "boabem.boabem", unsendable)]
pub struct PyContext {
    context: Context,
    rejections: Rc<PromiseRejections>,
}

#[derive(Default)]
struct PromiseRejections {
    unhandled: RefCell<Vec<JsObject<Promise>>>,
}

impl PromiseRejections {
    fn take_error(&self) -> Option<JsError> {
        let promise = self.unhandled.take().into_iter().next()?;
        match JsPromise::from(promise).state() {
            PromiseState::Rejected(reason) => Some(JsError::from_opaque(reason)),
            _ => None,
        }
    }
}

impl HostHooks for PromiseRejections {
    fn promise_rejection_tracker(
        &self,
        promise: &JsObject<Promise>,
        operation: OperationType,
        _context: &mut Context,
    ) {
        // Defer reporting until jobs finish so a later .catch() can handle the rejection.
        let mut unhandled = self.unhandled.borrow_mut();
        match operation {
            OperationType::Reject => unhandled.push(promise.clone()),
            OperationType::Handle => unhandled.retain(|p| p != promise),
        }
    }
}

#[pymethods]
impl PyContext {
    #[new]
    fn new() -> PyResult<Self> {
        let rejections = Rc::new(PromiseRejections::default());
        let mut context = Context::builder()
            .host_hooks(rejections.clone())
            .build()
            .map_err(js_error_to_py)?;

        let fetcher = catch_unwind(boa_runtime::fetch::BlockingReqwestFetcher::default)
            .map_err(|e| PyRuntimeError::new_err(format!("Panic occurred: {:?}", e)))?;

        boa_runtime::register(
            (
                boa_runtime::extensions::ConsoleExtension::default(),
                boa_runtime::extensions::FetchExtension(fetcher),
            ),
            None,
            &mut context,
        )
        .map_err(js_error_to_py)?;

        Ok(Self {
            context,
            rejections,
        })
    }

    pub fn eval(&mut self, source: &str) -> PyResult<Py<PyAny>> {
        self.eval_from_bytes(source)
    }

    pub fn eval_from_bytes(&mut self, source: &str) -> PyResult<Py<PyAny>> {
        let source = Source::from_bytes(source);
        let result = self.context.eval(source);
        self.finish_eval(result)
    }

    pub fn eval_from_filepath(&mut self, source: PathBuf) -> PyResult<Py<PyAny>> {
        let source = Source::from_filepath(&source)?;
        let result = self.context.eval(source);
        self.finish_eval(result)
    }
}

fn to_pyobject<'a, T: IntoPyObjectExt<'a>>(py: Python<'a>, value: T) -> PyResult<Py<PyAny>> {
    value.into_py_any(py)
}

fn js_error_to_py(error: JsError) -> PyErr {
    PyRuntimeError::new_err(error.to_string())
}

fn to_pybigint(value: &str) -> PyResult<Py<PyAny>> {
    let int: BigInt = BigInt::from_str_radix(value, 10)
        .map_err(|_| PyRuntimeError::new_err("Failed to parse BigInt"))?;
    Python::attach(|py| to_pyobject(py, int))
}

impl PyContext {
    fn finish_eval(&mut self, result: JsResult<JsValue>) -> PyResult<Py<PyAny>> {
        // Drain jobs and rejection state even after a throw, keeping the next eval independent.
        let evaluation_jobs = self.context.run_jobs().map_err(js_error_to_py);
        let converted = match result {
            Ok(v) => evaluation_jobs.and_then(|()| self.jsvalue_to_pyobject(v)),
            Err(e) => Err(js_error_to_py(e)),
        };

        // Conversion can invoke JS getters, e.g. one that queues a rejection handler.
        let conversion_jobs = self.context.run_jobs().map_err(js_error_to_py);
        let rejection = self.rejections.take_error();

        // Report the original error only after cleanup so it cannot leak into the next eval.
        let value = converted?;
        conversion_jobs?;
        if let Some(error) = rejection {
            return Err(js_error_to_py(error));
        }
        Ok(value)
    }

    fn jsvalue_to_pyobject(&mut self, value: JsValue) -> PyResult<Py<PyAny>> {
        if let Some(promise) = value.as_promise() {
            return self.jspromise_to_pyobject(promise);
        }
        match value.variant() {
            JsVariant::Null => Python::attach(|py| to_pyobject(py, PyNone::get(py))),
            JsVariant::Undefined => Python::attach(|py| to_pyobject(py, PyUndefined::new())),
            JsVariant::Boolean(v) => Python::attach(|py| to_pyobject(py, v)),
            JsVariant::String(v) => Python::attach(|py| to_pyobject(py, v.to_std_string_escaped())),
            JsVariant::Float64(v) => Python::attach(|py| to_pyobject(py, v)),
            JsVariant::Integer32(v) => Python::attach(|py| to_pyobject(py, v)),
            JsVariant::BigInt(v) => to_pybigint(&v.to_string_radix(10)),
            JsVariant::Object(obj) if obj.is_array() => self.jsobj_to_pylist(&value),
            JsVariant::Object(_) => self.jsobj_to_pydict(&value),
            JsVariant::Symbol(_) => Err(PyRuntimeError::new_err(
                "TypeError: cannot convert Symbol to JSON",
            )),
        }
    }

    fn jspromise_to_pyobject(&mut self, promise: JsPromise) -> PyResult<Py<PyAny>> {
        // A getter can create a new Promise after the initial job queue was drained.
        if matches!(promise.state(), PromiseState::Pending) {
            self.context.run_jobs().map_err(js_error_to_py)?;
        }
        match promise.state() {
            PromiseState::Fulfilled(value) => self.jsvalue_to_pyobject(value),
            PromiseState::Rejected(reason) => Err(js_error_to_py(JsError::from_opaque(reason))),
            PromiseState::Pending => Err(PyRuntimeError::new_err(
                "Promise is still pending after running jobs",
            )),
        }
    }

    fn jsobj_to_pylist(&mut self, obj: &JsValue) -> PyResult<Py<PyAny>> {
        let arr: Vec<JsValue> = Vec::try_from_js(obj, &mut self.context).map_err(js_error_to_py)?;

        Python::attach(|py| {
            let py_list = PyList::empty(py);
            for item in arr {
                let py_item = self.jsvalue_to_pyobject(item)?;
                py_list.append(py_item)?;
            }
            Ok(py_list.into())
        })
    }

    fn jsobj_to_pydict(&mut self, obj: &JsValue) -> PyResult<Py<PyAny>> {
        let map: HashMap<String, JsValue> =
            HashMap::try_from_js(obj, &mut self.context).map_err(js_error_to_py)?;

        Python::attach(|py| {
            let py_dict = PyDict::new(py);
            for (key, value) in map {
                let py_value = self.jsvalue_to_pyobject(value)?;
                py_dict.set_item(key, py_value)?;
            }
            Ok(py_dict.into())
        })
    }
}
