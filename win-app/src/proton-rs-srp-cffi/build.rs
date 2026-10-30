use std::env;

fn main() {
    let target_os = env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    if target_os != "windows" {
        return;
    }

    let mut res = winres::WindowsResource::new();

    let major = env::var("CARGO_PKG_VERSION_MAJOR").unwrap();
    let minor = env::var("CARGO_PKG_VERSION_MINOR").unwrap();
    let patch = env::var("CARGO_PKG_VERSION_PATCH").unwrap();

    let build_num = env::var("CARGO_PKG_VERSION_PRE")
        .ok()
        .and_then(|s| s.split('.').next_back()?.parse::<u16>().ok())
        .unwrap_or(0);

    let ver_dot = format!("{major}.{minor}.{patch}.{build_num}");

    let ver_num: u64 =
        ((major.parse::<u64>().unwrap()) << 48) |
        ((minor.parse::<u64>().unwrap()) << 32) |
        ((patch.parse::<u64>().unwrap()) << 16) |
        (build_num as u64);

    res.set("LegalCopyright",   "© 2025 Proton AG");
    res.set("FileVersion",      &ver_dot);
    res.set("ProductVersion",   &ver_dot);

    res.set_version_info(winres::VersionInfo::FILEVERSION, ver_num);
    res.set_version_info(winres::VersionInfo::PRODUCTVERSION, ver_num);

    res.compile().expect("resource compilation failed");

    println!("cargo:rustc-link-arg=/VERSION:{major}.{minor}");
}