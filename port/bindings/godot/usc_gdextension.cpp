// Godot binding for the Unscripted runtime.
//
// A GDExtension, written against the RAW GDExtension C interface rather than
// against `godot-cpp`. That is deliberate: `godot-cpp` is a large build of its
// own, it has to be rebuilt per Godot version, and vendoring it into a runtime
// whose whole claim is "no dependencies" would be the first exception. The
// header this includes is produced by Godot itself:
//
//     godot --headless --dump-gdextension-interface
//
// What a game gets is one class, `Unscripted`, with the same surface as the C
// ABI and String in place of `const char*`:
//
//     var world = Unscripted.new()
//     world.open("res://packs/cyberpunk-block", files, "{}")
//     print(world.submit_player_text("look"))
//
// Every method returns a String -- JSON for the structured ones -- and errors
// come back through `last_error()` rather than as an exception, because a
// GDExtension that throws across the boundary takes the editor with it.
#include "gdextension_interface.h"

#include <cstdlib>
#include <cstring>
#include <new>
#include <vector>
#include <string>

#include "usc.h"

namespace {

// ---------------------------------------------------------------- interface --
//
// Everything Godot lends us, fetched once at init. There is no other way in: a
// GDExtension gets exactly one function pointer and asks for the rest by name.

GDExtensionInterfaceGetProcAddress get_proc = nullptr;
GDExtensionClassLibraryPtr library = nullptr;

GDExtensionInterfaceStringNameNewWithLatin1Chars string_name_new = nullptr;
GDExtensionInterfaceStringNewWithUtf8Chars string_new = nullptr;
GDExtensionInterfaceStringToUtf8Chars string_to_utf8 = nullptr;
GDExtensionInterfaceClassdbRegisterExtensionClass2 register_class = nullptr;
GDExtensionInterfaceClassdbRegisterExtensionClassMethod register_method = nullptr;
GDExtensionInterfaceVariantGetPtrDestructor get_destructor = nullptr;
GDExtensionInterfaceGetVariantFromTypeConstructor variant_from = nullptr;
GDExtensionInterfaceGetVariantToTypeConstructor variant_to = nullptr;
GDExtensionInterfaceMemAlloc mem_alloc = nullptr;
GDExtensionInterfaceMemFree mem_free = nullptr;
GDExtensionInterfaceClassdbConstructObject construct_object = nullptr;
GDExtensionInterfaceObjectSetInstance set_instance = nullptr;

GDExtensionPtrDestructor destroy_string = nullptr;
GDExtensionPtrDestructor destroy_string_name = nullptr;
GDExtensionVariantFromTypeConstructorFunc variant_from_string = nullptr;
GDExtensionVariantFromTypeConstructorFunc variant_from_int = nullptr;
GDExtensionTypeFromVariantConstructorFunc string_from_variant = nullptr;

template <typename Fn>
Fn proc(const char* name) {
    return reinterpret_cast<Fn>(get_proc(name));
}

/// A Godot StringName, destroyed on the way out. Registration needs a great many
/// of them and every one has to be freed.
struct StringName {
    // Opaque, and sized by the engine. 8 bytes on every build Godot ships.
    uint8_t storage[8] = {};
    explicit StringName(const char* text) { string_name_new(&storage, text, false); }
    ~StringName() { destroy_string_name(&storage); }
    StringName(const StringName&) = delete;
    StringName& operator=(const StringName&) = delete;
    void* ptr() { return &storage; }
};

/// A Godot String holding UTF-8 we produced.
struct GodotString {
    uint8_t storage[8] = {};
    explicit GodotString(const char* text) { string_new(&storage, text); }
    ~GodotString() { destroy_string(&storage); }
    GodotString(const GodotString&) = delete;
    void* ptr() { return &storage; }
};

/// The UTF-8 behind a Godot String argument. Asked for its length first, which
/// is what the interface requires: passing a null buffer returns the size.
std::string utf8_of(GDExtensionConstVariantPtr variant) {
    uint8_t as_string[8] = {};
    string_from_variant(&as_string, const_cast<GDExtensionVariantPtr>(variant));
    GDExtensionInt length = string_to_utf8(&as_string, nullptr, 0);
    std::string out;
    if (length > 0) {
        out.resize(static_cast<std::size_t>(length));
        string_to_utf8(&as_string, &out[0], length);
    }
    destroy_string(&as_string);
    return out;
}

// ------------------------------------------------------------- the instance --

/// One `Unscripted` object. Holds a runtime handle and nothing else.
struct Instance {
    usc_runtime* runtime = nullptr;
    std::string answer;
};

/// Godot's constructor for the class.
///
/// This has to return a GODOT OBJECT, not our own data -- the first version
/// returned the `Instance` and Godot dereferenced it as an object, which is a
/// segfault inside the engine with our name nowhere in the backtrace. The
/// sequence is: build the parent, attach our data to it, hand back the parent.
GDExtensionObjectPtr create_instance(void*) {
    StringName parent("RefCounted");
    GDExtensionObjectPtr object = construct_object(parent.ptr());
    void* memory = mem_alloc(sizeof(Instance));
    Instance* instance = new (memory) Instance();
    StringName class_name("Unscripted");
    set_instance(object, class_name.ptr(), instance);
    return object;
}

/// And the destructor, which frees OUR data only: Godot owns the object.
void free_instance(void*, void* self) {
    Instance* instance = static_cast<Instance*>(self);
    if (!instance) return;
    usc_close(instance->runtime);
    instance->~Instance();
    mem_free(instance);
}

void* get_virtual(void*, GDExtensionConstStringNamePtr) { return nullptr; }

// ------------------------------------------------------------- the methods --
//
// Each is a `call_func`: Variants in, a Variant out. `ptrcall_func` is left null
// and the method is registered without the ptrcall flag, so Godot always takes
// this path. Slower per call and impossible to get subtly wrong, which is the
// right trade for a binding whose calls happen once per player turn.

void answer_string(Instance* instance, const std::string& text,
                   GDExtensionVariantPtr out) {
    GodotString value(text.c_str());
    variant_from_string(out, value.ptr());
}

void answer_int(long long number, GDExtensionVariantPtr out) {
    GDExtensionInt value = number;
    variant_from_int(out, &value);
}

/// `open(pack_path, character_files, config_json) -> String`
///
/// Returns "" on success and the reason otherwise, because a GDScript caller
/// checks a string far more readily than it checks an error code.
void method_open(void*, GDExtensionClassInstancePtr self,
                 const GDExtensionConstVariantPtr* args, GDExtensionInt count,
                 GDExtensionVariantPtr out, GDExtensionCallError* error) {
    Instance* instance = static_cast<Instance*>(self);
    if (count < 2) {
        error->error = GDEXTENSION_CALL_ERROR_TOO_FEW_ARGUMENTS;
        error->expected = 2;
        return;
    }
    std::string pack = utf8_of(args[0]);
    // The character list arrives as a newline-separated String rather than as a
    // PackedStringArray: marshalling an array through the raw interface costs
    // three more constructors and a destructor for a list a caller builds with
    // `"\n".join(files)`.
    std::string joined = utf8_of(args[1]);
    std::string config = count > 2 ? utf8_of(args[2]) : std::string();

    std::vector<std::string> names;
    std::size_t at = 0;
    while (at <= joined.size()) {
        std::size_t stop = joined.find('\n', at);
        if (stop == std::string::npos) stop = joined.size();
        std::string one = joined.substr(at, stop - at);
        if (!one.empty()) names.push_back(one);
        if (stop == joined.size()) break;
        at = stop + 1;
    }
    std::vector<const char*> pointers;
    for (const std::string& one : names) pointers.push_back(one.c_str());
    pointers.push_back(nullptr);

    usc_close(instance->runtime);
    instance->runtime = nullptr;
    usc_status status = usc_open(pack.c_str(), pointers.data(),
                                 config.empty() ? nullptr : config.c_str(),
                                 &instance->runtime);
    answer_string(instance,
                  status == USC_OK ? std::string() : usc_last_error(nullptr), out);
}

/// A method that takes no arguments and answers with JSON.
template <usc_status (*Call)(usc_runtime*, const char**)>
void method_json(void*, GDExtensionClassInstancePtr self,
                 const GDExtensionConstVariantPtr*, GDExtensionInt,
                 GDExtensionVariantPtr out, GDExtensionCallError*) {
    Instance* instance = static_cast<Instance*>(self);
    const char* json = nullptr;
    if (Call(instance->runtime, &json) != USC_OK)
        answer_string(instance, std::string("{\"error\":\"")
                      + usc_last_error(instance->runtime) + "\"}", out);
    else
        answer_string(instance, json ? json : "", out);
}

/// A method that takes one string and answers with JSON.
template <usc_status (*Call)(usc_runtime*, const char*, const char**)>
void method_json_1(void*, GDExtensionClassInstancePtr self,
                   const GDExtensionConstVariantPtr* args, GDExtensionInt count,
                   GDExtensionVariantPtr out, GDExtensionCallError* error) {
    Instance* instance = static_cast<Instance*>(self);
    if (count < 1) {
        error->error = GDEXTENSION_CALL_ERROR_TOO_FEW_ARGUMENTS;
        error->expected = 1;
        return;
    }
    std::string argument = utf8_of(args[0]);
    const char* json = nullptr;
    if (Call(instance->runtime, argument.c_str(), &json) != USC_OK)
        answer_string(instance, std::string("{\"error\":\"")
                      + usc_last_error(instance->runtime) + "\"}", out);
    else
        answer_string(instance, json ? json : "", out);
}

void method_world_time(void*, GDExtensionClassInstancePtr self,
                       const GDExtensionConstVariantPtr*, GDExtensionInt,
                       GDExtensionVariantPtr out, GDExtensionCallError*) {
    answer_int(usc_world_time(static_cast<Instance*>(self)->runtime), out);
}

void method_advance_time(void*, GDExtensionClassInstancePtr self,
                         const GDExtensionConstVariantPtr* args, GDExtensionInt count,
                         GDExtensionVariantPtr out, GDExtensionCallError* error) {
    Instance* instance = static_cast<Instance*>(self);
    if (count < 1) {
        error->error = GDEXTENSION_CALL_ERROR_TOO_FEW_ARGUMENTS;
        error->expected = 1;
        return;
    }
    // The argument arrives as a Variant; read it as a String and parse, so the
    // binding takes `advance_time("60")` and `advance_time(60)` alike -- GDScript
    // passes an int and the raw interface would otherwise need a second
    // constructor to read it.
    std::string minutes = utf8_of(args[0]);
    long long value = std::strtoll(minutes.c_str(), nullptr, 10);
    usc_status status = usc_advance_time(instance->runtime, value);
    answer_string(instance,
                  status == USC_OK ? std::string()
                                   : usc_last_error(instance->runtime), out);
}

void method_last_error(void*, GDExtensionClassInstancePtr self,
                       const GDExtensionConstVariantPtr*, GDExtensionInt,
                       GDExtensionVariantPtr out, GDExtensionCallError*) {
    Instance* instance = static_cast<Instance*>(self);
    answer_string(instance, usc_last_error(instance->runtime), out);
}

void method_runtime_version(void*, GDExtensionClassInstancePtr self,
                            const GDExtensionConstVariantPtr*, GDExtensionInt,
                            GDExtensionVariantPtr out, GDExtensionCallError*) {
    answer_string(static_cast<Instance*>(self), usc_runtime_version(), out);
}

void method_abi_version(void*, GDExtensionClassInstancePtr,
                        const GDExtensionConstVariantPtr*, GDExtensionInt,
                        GDExtensionVariantPtr out, GDExtensionCallError*) {
    answer_int(usc_abi_version(), out);
}

// The three-argument ones are one-offs and get their own bodies.
void method_respond(void*, GDExtensionClassInstancePtr self,
                    const GDExtensionConstVariantPtr* args, GDExtensionInt count,
                    GDExtensionVariantPtr out, GDExtensionCallError* error) {
    Instance* instance = static_cast<Instance*>(self);
    if (count < 1) {
        error->error = GDEXTENSION_CALL_ERROR_TOO_FEW_ARGUMENTS;
        error->expected = 1;
        return;
    }
    std::string agent = utf8_of(args[0]);
    std::string topic = count > 1 ? utf8_of(args[1]) : std::string();
    const char* json = nullptr;
    if (usc_respond(instance->runtime, agent.c_str(),
                    topic.empty() ? nullptr : topic.c_str(), &json) != USC_OK)
        answer_string(instance, std::string("{\"error\":\"")
                      + usc_last_error(instance->runtime) + "\"}", out);
    else
        answer_string(instance, json ? json : "", out);
}

void method_face_packet(void*, GDExtensionClassInstancePtr self,
                        const GDExtensionConstVariantPtr* args, GDExtensionInt count,
                        GDExtensionVariantPtr out, GDExtensionCallError* error) {
    Instance* instance = static_cast<Instance*>(self);
    if (count < 1) {
        error->error = GDEXTENSION_CALL_ERROR_TOO_FEW_ARGUMENTS;
        error->expected = 1;
        return;
    }
    std::string agent = utf8_of(args[0]);
    std::string gaze = count > 1 ? utf8_of(args[1]) : std::string();
    const char* json = nullptr;
    if (usc_face_packet(instance->runtime, agent.c_str(),
                        gaze.empty() ? nullptr : gaze.c_str(), &json) != USC_OK)
        answer_string(instance, std::string("{\"error\":\"")
                      + usc_last_error(instance->runtime) + "\"}", out);
    else
        answer_string(instance, json ? json : "", out);
}

void method_knowledge_state(void*, GDExtensionClassInstancePtr self,
                            const GDExtensionConstVariantPtr* args,
                            GDExtensionInt count, GDExtensionVariantPtr out,
                            GDExtensionCallError*) {
    Instance* instance = static_cast<Instance*>(self);
    long long limit = 40;
    if (count > 0) {
        std::string text = utf8_of(args[0]);
        long long parsed = std::strtoll(text.c_str(), nullptr, 10);
        if (parsed > 0) limit = parsed;
    }
    const char* json = nullptr;
    if (usc_knowledge_state(instance->runtime, limit, &json) != USC_OK)
        answer_string(instance, std::string("{\"error\":\"")
                      + usc_last_error(instance->runtime) + "\"}", out);
    else
        answer_string(instance, json ? json : "", out);
}

// -------------------------------------------------------------- registration --

void bind_method(const char* name, GDExtensionClassMethodCall call,
                 uint32_t argument_count, bool returns_string) {
    StringName class_name("Unscripted");
    StringName method_name(name);

    GDExtensionPropertyInfo return_info = {};
    return_info.type = returns_string ? GDEXTENSION_VARIANT_TYPE_STRING
                                      : GDEXTENSION_VARIANT_TYPE_INT;
    StringName empty("");
    GodotString no_hint("");
    return_info.name = empty.ptr();
    return_info.class_name = empty.ptr();
    return_info.hint_string = no_hint.ptr();
    return_info.usage = 6;   // PROPERTY_USAGE_DEFAULT

    // Arguments are declared as Variants and read as strings. Godot only needs
    // the COUNT to be right; the types below are what the editor shows.
    static GDExtensionPropertyInfo arguments[3];
    static GDExtensionClassMethodArgumentMetadata metadata[3] = {};
    for (uint32_t i = 0; i < argument_count && i < 3; ++i) {
        arguments[i] = GDExtensionPropertyInfo{};
        arguments[i].type = GDEXTENSION_VARIANT_TYPE_STRING;
        arguments[i].name = empty.ptr();
        arguments[i].class_name = empty.ptr();
        arguments[i].hint_string = no_hint.ptr();
        arguments[i].usage = 6;
    }

    GDExtensionClassMethodInfo info = {};
    info.name = method_name.ptr();
    info.call_func = call;
    info.ptrcall_func = nullptr;
    info.method_flags = GDEXTENSION_METHOD_FLAG_NORMAL;
    info.has_return_value = 1;
    info.return_value_info = &return_info;
    info.argument_count = argument_count;
    info.arguments_info = argument_count ? arguments : nullptr;
    info.arguments_metadata = argument_count ? metadata : nullptr;
    register_method(library, class_name.ptr(), &info);
}

void initialise(void*, GDExtensionInitializationLevel level) {
    if (level != GDEXTENSION_INITIALIZATION_SCENE) return;

    StringName class_name("Unscripted");
    StringName parent("RefCounted");

    GDExtensionClassCreationInfo2 info = {};
    info.is_exposed = 1;
    info.create_instance_func = create_instance;
    info.free_instance_func = free_instance;
    info.get_virtual_func = reinterpret_cast<GDExtensionClassGetVirtual>(get_virtual);
    register_class(library, class_name.ptr(), parent.ptr(), &info);

    bind_method("open", method_open, 3, true);
    bind_method("submit_player_text", method_json_1<usc_submit_player_text>, 1, true);
    bind_method("respond", method_respond, 2, true);
    bind_method("agent_state", method_json_1<usc_agent_state>, 1, true);
    bind_method("inspect_agent", method_json_1<usc_inspect_agent>, 1, true);
    bind_method("world_state", method_json<usc_world_state>, 0, true);
    bind_method("scene_state", method_json<usc_scene_state>, 0, true);
    bind_method("export_state", method_json<usc_export_state>, 0, true);
    bind_method("pending_actions", method_json<usc_pending_actions>, 0, true);
    bind_method("inspect_state", method_json_1<usc_inspect_state>, 1, true);
    bind_method("import_state", method_json_1<usc_import_state>, 1, true);
    bind_method("knowledge_state", method_knowledge_state, 1, true);
    bind_method("face_packet", method_face_packet, 2, true);
    bind_method("advance_time", method_advance_time, 1, true);
    bind_method("world_time", method_world_time, 0, false);
    bind_method("last_error", method_last_error, 0, true);
    bind_method("runtime_version", method_runtime_version, 0, true);
    bind_method("abi_version", method_abi_version, 0, false);
}

void shut_down(void*, GDExtensionInitializationLevel) {}

}  // namespace

extern "C" __attribute__((visibility("default"))) GDExtensionBool usc_gdextension_init(
        GDExtensionInterfaceGetProcAddress p_get_proc,
        GDExtensionClassLibraryPtr p_library,
        GDExtensionInitialization* r_initialization) {
    get_proc = p_get_proc;
    library = p_library;

    string_name_new = proc<GDExtensionInterfaceStringNameNewWithLatin1Chars>(
        "string_name_new_with_latin1_chars");
    string_new = proc<GDExtensionInterfaceStringNewWithUtf8Chars>(
        "string_new_with_utf8_chars");
    string_to_utf8 = proc<GDExtensionInterfaceStringToUtf8Chars>("string_to_utf8_chars");
    register_class = proc<GDExtensionInterfaceClassdbRegisterExtensionClass2>(
        "classdb_register_extension_class2");
    register_method = proc<GDExtensionInterfaceClassdbRegisterExtensionClassMethod>(
        "classdb_register_extension_class_method");
    get_destructor = proc<GDExtensionInterfaceVariantGetPtrDestructor>(
        "variant_get_ptr_destructor");
    variant_from = proc<GDExtensionInterfaceGetVariantFromTypeConstructor>(
        "get_variant_from_type_constructor");
    variant_to = proc<GDExtensionInterfaceGetVariantToTypeConstructor>(
        "get_variant_to_type_constructor");
    mem_alloc = proc<GDExtensionInterfaceMemAlloc>("mem_alloc");
    mem_free = proc<GDExtensionInterfaceMemFree>("mem_free");
    construct_object = proc<GDExtensionInterfaceClassdbConstructObject>(
        "classdb_construct_object");
    set_instance = proc<GDExtensionInterfaceObjectSetInstance>("object_set_instance");
    if (!string_name_new || !string_new || !string_to_utf8 || !register_class
        || !register_method || !get_destructor || !variant_from || !variant_to
        || !mem_alloc || !mem_free || !construct_object || !set_instance)
        return 0;   // a Godot too old to speak this interface; refuse cleanly

    destroy_string = get_destructor(GDEXTENSION_VARIANT_TYPE_STRING);
    destroy_string_name = get_destructor(GDEXTENSION_VARIANT_TYPE_STRING_NAME);
    variant_from_string = variant_from(GDEXTENSION_VARIANT_TYPE_STRING);
    variant_from_int = variant_from(GDEXTENSION_VARIANT_TYPE_INT);
    string_from_variant = variant_to(GDEXTENSION_VARIANT_TYPE_STRING);

    r_initialization->initialize = initialise;
    r_initialization->deinitialize = shut_down;
    r_initialization->minimum_initialization_level =
        GDEXTENSION_INITIALIZATION_SCENE;
    return 1;
}
