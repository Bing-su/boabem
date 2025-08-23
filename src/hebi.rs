use boa_engine::{Context, JsValue, Source};
use eyre::{Result, eyre};
use pyo3::prelude::*;
use pythonize::pythonize;
use std::path::PathBuf;

#[pyclass(name = "Undefined", module = "boabem.boabem", str, eq, frozen)]
#[derive(Debug, PartialEq)]
pub struct PyUndefined {}

#[pymethods]
impl PyUndefined {
    #[new]
    fn new() -> Self {
        PyUndefined {}
    }

    fn __repr__(&self) -> &str {
        "Undefined"
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
        boa_runtime::register(&mut context, boa_runtime::RegisterOptions::new())
            .expect("should not fail while registering the runtime");

        PyContext { context }
    }

    pub fn eval(&mut self, source: &str) -> Result<PyObject> {
        self.eval_from_bytes(source)
    }

    pub fn eval_from_bytes(&mut self, source: &str) -> Result<PyObject> {
        let source = Source::from_bytes(source);
        let value: JsValue = self
            .context
            .eval(source)
            .map_err(|e| eyre!(e.to_string()))?;
        self.jsvalue_to_pyobject(value)
    }

    pub fn eval_from_filepath(&mut self, source: PathBuf) -> Result<PyObject> {
        let source = Source::from_filepath(&source)?;
        let value: JsValue = self
            .context
            .eval(source)
            .map_err(|e| eyre!(e.to_string()))?;
        self.jsvalue_to_pyobject(value)
    }
}

fn pybigint(value: &str) -> Result<PyObject> {
    Python::with_gil(|py| {
        let builtins = PyModule::import(py, "builtins")?;
        let int_class = builtins.getattr("int")?;
        let pyint = int_class.call1((value,))?;
        Ok(pyint.into())
    })
}

fn pyint(value: i32) -> Result<PyObject> {
    Python::with_gil(|py| {
        let v = value.into_pyobject(py)?;
        Ok(v.into())
    })
}

fn pyfloat(value: f64) -> Result<PyObject> {
    Python::with_gil(|py| {
        let v = value.into_pyobject(py)?;
        Ok(v.into())
    })
}

impl PyContext {
    fn jsvalue_to_pyobject(&mut self, value: JsValue) -> Result<PyObject> {
        match value {
            JsValue::Undefined => {
                Python::with_gil(|py| Ok(Py::new(py, PyUndefined::new())?.into_any()))
            }
            JsValue::BigInt(js_bigint) => {
                let bigint_str = js_bigint.to_string_radix(10);
                pybigint(&bigint_str)
            }
            JsValue::Rational(f) => pyfloat(f),
            JsValue::Integer(i) => pyint(i),
            other => {
                let json = other
                    .to_json(&mut self.context)
                    .map_err(|e| eyre!(e.to_string()))?;
                Python::with_gil(|py| {
                    pythonize(py, &json)
                        .map(PyObject::from)
                        .map_err(|e| eyre!(e.to_string()))
                })
            }
        }
    }
}
