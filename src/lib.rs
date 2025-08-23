use pyo3::panic::PanicException;
use pyo3::prelude::*;
mod hebi;

#[pymodule]
fn boabem(py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_class::<hebi::PyUndefined>()?;
    m.add_class::<hebi::PyContext>()?;
    m.add("PanicException", py.get_type::<PanicException>())?;
    Ok(())
}
