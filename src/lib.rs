use pyo3::prelude::*;
mod hebi;

#[pymodule]
fn boabem(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_class::<hebi::PyUndefined>()?;
    m.add_class::<hebi::PyContext>()?;
    Ok(())
}
