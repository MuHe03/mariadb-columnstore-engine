/* Copyright (C) 2014 InfiniDB, Inc.

   This program is free software; you can redistribute it and/or
   modify it under the terms of the GNU General Public License
   as published by the Free Software Foundation; version 2 of
   the License.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software
   Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
   MA 02110-1301, USA. */

/******************************************************************************************
******************************************************************************************/
/**
 * @file
 */
#pragma once

#include <string>
#include <sstream>
#include <exception>
#include <iostream>
#include <unistd.h>

#include "messagequeue.h"
#include "bytestream.h"
#include "configcpp.h"

#include "ddlpackageprocessor.h"
#include "createtableprocessor.h"
#if 0
#include "createindexprocessor.h"
#include "dropindexprocessor.h"
#endif
#include "altertableprocessor.h"
#include "droptableprocessor.h"

#include "messagelog.h"
