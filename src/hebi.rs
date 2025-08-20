use boa_engine::{Context, JsValue, Source};
use eyre::{Result, eyre};
use pyo3::prelude::*;
use pythonize::pythonize;

#[pyclass(name = "Undefined", module = "boabem.boabem", str)]
pub struct PyUndefined {}

#[pymethods]
impl PyUndefined {
    #[new]
    fn new() -> Self {
        PyUndefined {}
    }

    fn __repr__(&self) -> String {
        self.to_string()
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

        PyContext { context: context }
    }

    pub fn eval(&mut self, source: &str) -> Result<PyObject> {
        let source = Source::from_bytes(source);

        let value = match self.context.eval(source) {
            Ok(JsValue::Undefined) => {
                return Python::with_gil(|py| Ok(Py::new(py, PyUndefined::new())?.into_any()));
            }
            Ok(value) => value
                .to_json(&mut self.context)
                .map_err(|e| eyre!(e.to_string()))?,
            Err(e) => return Err(eyre!(e.to_string())),
        };

        Python::with_gil(|py| {
            pythonize(py, &value)
                .map(PyObject::from)
                .map_err(|e| eyre!(e.to_string()))
        })
    }
}
