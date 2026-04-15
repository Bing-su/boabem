use pyo3::prelude::*;
mod hebi;

#[pymodule]
mod boabem {
    #[pymodule_export]
    #[allow(non_upper_case_globals)]
    const __version__: &str = env!("CARGO_PKG_VERSION");

    #[pymodule_export]
    use super::hebi::PyUndefined;

    #[pymodule_export]
    use super::hebi::PyContext;

    #[pymodule_export]
    use pyo3::panic::PanicException;
}
