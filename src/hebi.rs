use std::collections::HashMap;
use std::path::PathBuf;

use boa_engine::value::TryFromJs;
use boa_engine::{Context, JsValue, JsVariant, Source};
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
    fn new() -> Self {
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
}

#[pymethods]
impl PyContext {
    #[new]
    fn new() -> Self {
        let mut context = Context::default();
        boa_runtime::register(
            (
                boa_runtime::extensions::ConsoleExtension::default(),
                boa_runtime::extensions::FetchExtension(
                    boa_runtime::fetch::BlockingReqwestFetcher::default(),
                ),
            ),
            None,
            &mut context,
        )
        .expect("should not fail while registering the runtime");

        Self { context }
    }

    pub fn eval(&mut self, source: &str) -> PyResult<Py<PyAny>> {
        self.eval_from_bytes(source)
    }

    pub fn eval_from_bytes(&mut self, source: &str) -> PyResult<Py<PyAny>> {
        let source = Source::from_bytes(source);
        let value: JsValue = self
            .context
            .eval(source)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        self.jsvalue_to_pyobject(value)
    }

    pub fn eval_from_filepath(&mut self, source: PathBuf) -> PyResult<Py<PyAny>> {
        let source = Source::from_filepath(&source)?;
        let value: JsValue = self
            .context
            .eval(source)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        self.jsvalue_to_pyobject(value)
    }
}

fn to_pyobject<'a, T: IntoPyObjectExt<'a>>(py: Python<'a>, value: T) -> PyResult<Py<PyAny>> {
    Ok(value.into_py_any(py)?)
}

impl PyContext {
    fn jsvalue_to_pyobject(&mut self, value: JsValue) -> PyResult<Py<PyAny>> {
        match value.variant() {
            JsVariant::Null => Python::attach(|py| to_pyobject(py, PyNone::get(py))),
            JsVariant::Undefined => Python::attach(|py| to_pyobject(py, PyUndefined::new())),
            JsVariant::Boolean(v) => Python::attach(|py| to_pyobject(py, v)),
            JsVariant::String(v) => Python::attach(|py| to_pyobject(py, v.to_std_string_escaped())),
            JsVariant::Float64(v) => Python::attach(|py| to_pyobject(py, v)),
            JsVariant::Integer32(v) => Python::attach(|py| to_pyobject(py, v)),
            JsVariant::BigInt(v) => Python::attach(|py| to_pyobject(py, v.as_inner())),
            JsVariant::Object(obj) if obj.is_array() => self.jsobj_to_pylist(&value),
            JsVariant::Object(_) => self.jsobj_to_pydict(&value),
            JsVariant::Symbol(_) => Err(PyRuntimeError::new_err(
                "TypeError: cannot convert Symbol to JSON",
            )),
        }
    }

    fn jsobj_to_pylist(&mut self, obj: &JsValue) -> PyResult<Py<PyAny>> {
        let arr: Vec<JsValue> = Vec::try_from_js(obj, &mut self.context)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

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
        let map: HashMap<String, JsValue> = HashMap::try_from_js(obj, &mut self.context)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

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
