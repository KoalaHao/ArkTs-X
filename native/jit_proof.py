"""LLDB command: observe JIT entry installation, then stop in that machine code.

Load with `command script import /absolute/path/native/jit_proof.py`, then run
`jit-proof` in an LLDB target configured with the port_smoke runtime arguments.
No runtime instrumentation or timing results are involved.
"""
import pathlib
import re
import signal
import lldb

ROOT = pathlib.Path(__file__).resolve().parents[1]

def prove(debugger, command, result, _internal):
    target = debugger.GetSelectedTarget()
    definitions = (ROOT / 'build/ark-source/runtime/include/asm_defines.h').read_text()
    offset = int(re.search(r'#define METHOD_COMPILED_ENTRY_POINT_OFFSET (\d+)', definitions)[1])
    install = target.BreakpointCreateByRegex('PandaRuntimeInterface::SetCompiledEntryPoint')
    if not install.GetNumLocations():
        result.SetError('JIT entry installation symbol was not found')
        return
    debugger.SetAsync(False)
    process = target.LaunchSimple(None, None, str(ROOT))
    entry_breakpoint = None
    entry_address = None
    method = None
    while process.GetState() == lldb.eStateStopped:
        thread = next((t for t in process if t.GetStopReason() == lldb.eStopReasonBreakpoint), None)
        if thread is None:
            signaled = next((t for t in process if t.GetStopReason() == lldb.eStopReasonSignal), None)
            if signaled is not None:
                number = signaled.GetStopReasonDataAtIndex(0)
                if number in (signal.SIGUSR1, signal.SIGUSR2):
                    process.GetUnixSignals().SetShouldStop(number, False)
                    process.GetUnixSignals().SetShouldNotify(number, False)
                    process.Continue()
                    continue
            reasons = '; '.join(str(t.GetStopDescription(200)) for t in process)
            result.SetError('Stopped for a non-breakpoint reason: ' + reasons)
            process.Kill()
            return
        frame = thread.GetFrameAtIndex(0)
        if entry_breakpoint and frame.GetPC() == entry_address:
            error = lldb.SBError()
            installed = process.ReadUnsignedFromMemory(method + offset, 8, error)
            if error.Fail() or installed != entry_address:
                result.SetError('Executed address does not match the installed Method entry')
                process.Kill()
                return
            assembly = str(frame.Disassemble())[:1600]
            thread.StepInstruction(False)
            after = thread.GetFrameAtIndex(0).GetPC()
            if after != entry_address + 4:
                result.SetError('Did not execute the first ARM64 JIT instruction')
                process.Kill()
                return
            result.AppendMessage(f'JIT_EXECUTION_PROVED entry={entry_address:#x} pc_after_instruction={after:#x}')
            result.AppendMessage(assembly)
            process.Kill()
            return
        # C++ member call: x0=this, x1=Method*, x2=generated entry.
        method = frame.FindRegister('x1').GetValueAsUnsigned()
        entry = frame.FindRegister('x2').GetValueAsUnsigned()
        region = lldb.SBMemoryRegionInfo()
        process.GetMemoryRegionInfo(entry, region)
        if not target.ResolveLoadAddress(entry).GetModule().IsValid() and region.IsExecutable():
            entry_address = entry
            entry_breakpoint = target.BreakpointCreateByAddress(entry)
            install.SetEnabled(False)
            result.AppendMessage(f'JIT_INSTALL_OBSERVED method={method:#x} entry={entry:#x}')
        else:
            result.SetError('JIT install did not target anonymous executable memory')
            process.Kill()
            return
        process.Continue()
    result.SetError('Process exited without executing an observed JIT entry: ' + str(process))

def __lldb_init_module(debugger, _internal):
    debugger.HandleCommand('command script add -f jit_proof.prove jit-proof')
    debugger.HandleCommand('command script add -f jit_proof.prove_osr osr-proof')

def prove_osr(debugger, command, result, _internal):
    target = debugger.GetSelectedTarget()
    prepare = target.BreakpointCreateByName('PrepareOsrEntry')
    if not prepare.GetNumLocations():
        result.SetError('OSR preparation symbol was not found')
        return
    debugger.SetAsync(False)
    process = target.LaunchSimple(None, None, str(ROOT))
    return_pc = None
    native_pc = None
    temporary = None
    while process.GetState() == lldb.eStateStopped:
        thread = next((t for t in process if t.GetStopReason() == lldb.eStopReasonBreakpoint), None)
        if thread is None:
            signaled = next((t for t in process if t.GetStopReason() == lldb.eStopReasonSignal), None)
            if signaled is not None:
                number = signaled.GetStopReasonDataAtIndex(0)
                if number in (signal.SIGUSR1, signal.SIGUSR2):
                    process.GetUnixSignals().SetShouldStop(number, False)
                    process.Continue()
                    continue
            result.SetError('Unexpected OSR debugger stop')
            process.Kill()
            return
        frame = thread.GetFrameAtIndex(0)
        pc = frame.GetPC()
        if native_pc is not None and pc == native_pc:
            assembly = str(frame.Disassemble())[:1000]
            thread.StepInstruction(False)
            after = thread.GetFrameAtIndex(0).GetPC()
            if after != pc + 4:
                result.SetError('Did not execute the first ARM64 OSR instruction')
                process.Kill()
                return
            result.AppendMessage(f'OSR_EXECUTION_PROVED entry={pc:#x} pc_after_instruction={after:#x}')
            result.AppendMessage(assembly)
            process.Kill()
            return
        if return_pc is not None and pc == return_pc:
            native_pc = frame.FindRegister('x0').GetValueAsUnsigned()
            region = lldb.SBMemoryRegionInfo()
            process.GetMemoryRegionInfo(native_pc, region)
            if target.ResolveLoadAddress(native_pc).GetModule().IsValid() or not region.IsExecutable():
                result.SetError('OSR did not prepare a JIT code address')
                process.Kill()
                return
            temporary.SetEnabled(False)
            temporary = target.BreakpointCreateByAddress(native_pc)
            result.AppendMessage(f'OSR_STATE_RECONSTRUCTED entry={native_pc:#x}')
        else:
            result.AppendMessage('OSR_PREPARE_OBSERVED bc=' + frame.FindRegister('x1').GetValue())
            return_pc = frame.FindRegister('lr').GetValueAsUnsigned()
            prepare.SetEnabled(False)
            temporary = target.BreakpointCreateByAddress(return_pc)
        process.Continue()
    result.SetError('Process exited without an observed OSR transition')
